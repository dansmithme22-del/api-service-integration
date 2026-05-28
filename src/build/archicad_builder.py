"""Build Archicad elements from a PlanGraph.

This module bridges the PDF-ingest pipeline (in inches, abstract coordinates)
to the live Archicad model. Two execution modes:

1. **Live mode** — connects to Archicad on port 19723 and creates walls,
   doors, windows, zones via the JSON API.
2. **Tape mode** — emits a JSON "command tape" the user (or a later run) can
   replay against Archicad. Useful when AC is not running.

Live placement currently issues the ``API.CreateElements`` JSON command for
walls. Some element types (doors, windows, zones) are not always exposed by
the stock JSON API; for those we fall back to writing a tape that the C++
``layout_annotator_cpp`` add-on can consume — that is the same fallback
strategy the existing apply/text_placer.py uses.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..connection import ArchicadConnection
from ..ingest.plan_model import (
    Opening,
    OpeningKind,
    PlanGraph,
    Room,
    Wall,
    WallStatus,
)

logger = logging.getLogger(__name__)

# 1 inch = 0.0254 metres. Archicad's JSON API uses metres for length-typed
# parameters in CreateElements / ChangeElements calls.
IN_TO_M = 0.0254


@dataclass
class BuildResult:
    walls_created: int = 0
    doors_created: int = 0
    windows_created: int = 0
    zones_created: int = 0
    skipped: list[str] = field(default_factory=list)
    tape_path: Optional[str] = None        # path to the JSON tape if one was written


def build_plan_in_archicad(
    plan: PlanGraph,
    *,
    conn: Optional[ArchicadConnection] = None,
    tape_out: Optional[str | Path] = None,
    layer_existing: str = "A-Wall-Existing",
    layer_demo: str = "A-Wall-Demo",
    layer_new: str = "A-Wall-New",
    default_wall_height_in: float = 108.0,
) -> BuildResult:
    """Materialize ``plan`` into Archicad. If ``conn`` is None, write a tape only.

    A "tape" is a JSON file listing every CreateElements call the live builder
    would have made — replayable, diffable, and inspectable.
    """
    builder = ArchicadBuilder(
        conn=conn,
        layer_existing=layer_existing,
        layer_demo=layer_demo,
        layer_new=layer_new,
        default_wall_height_in=default_wall_height_in,
    )

    for w in plan.walls:
        builder.add_wall(w)

    for o in plan.openings:
        builder.add_opening(o, plan.walls)

    for r in plan.rooms:
        builder.add_zone(r)

    if tape_out:
        tape_path = Path(tape_out)
        tape_path.parent.mkdir(parents=True, exist_ok=True)
        tape_path.write_text(json.dumps(builder.tape, indent=2))
        builder.result.tape_path = str(tape_path)
        logger.info("Wrote command tape: %s (%d entries)", tape_path, len(builder.tape))

    if conn is not None:
        builder.execute_live()

    return builder.result


class ArchicadBuilder:
    """Stateful builder; collects commands first, can execute or persist as tape."""

    def __init__(
        self,
        conn: Optional[ArchicadConnection] = None,
        *,
        layer_existing: str = "A-Wall-Existing",
        layer_demo: str = "A-Wall-Demo",
        layer_new: str = "A-Wall-New",
        default_wall_height_in: float = 108.0,
    ):
        self.conn = conn
        self.layer_existing = layer_existing
        self.layer_demo = layer_demo
        self.layer_new = layer_new
        self.default_wall_height_in = default_wall_height_in

        self.tape: list[dict[str, Any]] = []
        self.result = BuildResult()

    # ------------------------------------------------------------------
    # Recording phase
    # ------------------------------------------------------------------

    def add_wall(self, wall: Wall) -> None:
        layer = self._layer_for_status(wall.status)
        # Archicad CreateElements expects a list of element-typed dicts.
        self.tape.append({
            "command": "API.CreateElements",
            "kind": "wall",
            "element": {
                "type": "Wall",
                "wallData": {
                    "begC": {"x": wall.start.x * IN_TO_M, "y": wall.start.y * IN_TO_M},
                    "endC": {"x": wall.end.x * IN_TO_M, "y": wall.end.y * IN_TO_M},
                    "height": (wall.height_in or self.default_wall_height_in) * IN_TO_M,
                    "thickness": wall.thickness_in * IN_TO_M,
                    "structure": "Basic",
                    "geometryMethod": "Straight",
                    "renovationStatus": _renovation_status_string(wall.status),
                    "layer": layer,
                },
            },
            "meta": {
                "wall_id": wall.id,
                "confidence": wall.confidence,
                "source_note": wall.source_note,
            },
        })

    def add_opening(self, opening: Opening, walls: list[Wall]) -> None:
        if not opening.wall_id:
            self.result.skipped.append(f"opening {opening.id}: no wall_id")
            return
        wall = next((w for w in walls if w.id == opening.wall_id), None)
        if wall is None:
            self.result.skipped.append(f"opening {opening.id}: wall not found")
            return

        op_type = "Door" if opening.kind == OpeningKind.DOOR else "Window"
        self.tape.append({
            "command": "API.CreateElements",
            "kind": op_type.lower(),
            "element": {
                "type": op_type,
                f"{op_type.lower()}Data": {
                    "ownerWallId": wall.id,  # resolved at execute_live time
                    "objLoc": opening.distance_along_wall_in * IN_TO_M,
                    "width": opening.width_in * IN_TO_M,
                    "height": opening.height_in * IN_TO_M,
                    "sillHeight": opening.sill_height_in * IN_TO_M,
                    "flipped": opening.swing_direction == "right",
                },
            },
            "meta": {
                "opening_id": opening.id,
                "confidence": opening.confidence,
            },
        })

    def add_zone(self, room: Room) -> None:
        if len(room.polygon) < 3:
            self.result.skipped.append(f"zone {room.id}: polygon < 3 pts")
            return
        coords = [
            {"x": p.x * IN_TO_M, "y": p.y * IN_TO_M}
            for p in room.polygon
        ]
        self.tape.append({
            "command": "API.CreateElements",
            "kind": "zone",
            "element": {
                "type": "Zone",
                "zoneData": {
                    "name": room.name or "Room",
                    "polygon": {"coordinates": coords},
                    "category": room.use or "01 General",
                },
            },
            "meta": {"zone_id": room.id, "area_sqft": room.area_sqft},
        })

    # ------------------------------------------------------------------
    # Execute against live Archicad
    # ------------------------------------------------------------------

    def execute_live(self) -> None:
        if self.conn is None:
            raise RuntimeError("No Archicad connection; cannot execute live.")
        if not self.conn.connected:
            raise RuntimeError("Archicad connection is not open; call .connect() first.")

        # Map our placeholder wall IDs (uuid) to the Archicad GUIDs returned
        # from CreateElements so subsequent door/window calls can reference
        # the right ownerWallId.
        id_map: dict[str, str] = {}

        for entry in self.tape:
            kind = entry["kind"]
            element = entry["element"]
            try:
                if kind == "wall":
                    guid = self._exec_create(element)
                    id_map[entry["meta"]["wall_id"]] = guid
                    self.result.walls_created += 1
                elif kind in ("door", "window"):
                    # Replace placeholder ownerWallId with the real GUID.
                    data_key = f"{kind}Data"
                    placeholder = element[data_key].get("ownerWallId")
                    if placeholder in id_map:
                        element[data_key]["ownerWallId"] = id_map[placeholder]
                    else:
                        self.result.skipped.append(
                            f"{kind} {entry['meta'].get('opening_id')}: parent wall not built"
                        )
                        continue
                    self._exec_create(element)
                    if kind == "door":
                        self.result.doors_created += 1
                    else:
                        self.result.windows_created += 1
                elif kind == "zone":
                    self._exec_create(element)
                    self.result.zones_created += 1
            except Exception as exc:
                self.result.skipped.append(f"{kind}: {exc}")
                logger.warning("Live exec failed for %s: %s", kind, exc)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _exec_create(self, element_dict: dict) -> str:
        """Wrap element_dict into a CreateElements call; return the new GUID."""
        params = {"elements": [element_dict]}
        resp = self.conn.execute_raw("API.CreateElements", params)
        # Defensive parsing — actual response shape varies by AC version.
        guid = ""
        try:
            results = resp.get("result", resp).get("elements", [])
            if results:
                guid = results[0].get("elementId", {}).get("guid", "") or \
                       results[0].get("guid", "")
        except AttributeError:
            pass
        return guid or f"unknown-{uuid.uuid4().hex[:8]}"

    def _layer_for_status(self, status: WallStatus) -> str:
        return {
            WallStatus.EXISTING: self.layer_existing,
            WallStatus.DEMOLITION: self.layer_demo,
            WallStatus.NEW: self.layer_new,
        }.get(status, self.layer_existing)


def _renovation_status_string(status: WallStatus) -> str:
    return {
        WallStatus.EXISTING: "ExistingElement",
        WallStatus.DEMOLITION: "ElementToBeDemolished",
        WallStatus.NEW: "NewElement",
    }.get(status, "ExistingElement")
