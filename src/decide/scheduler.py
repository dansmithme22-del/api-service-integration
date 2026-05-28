"""Build a CD-set schedule from a PlanGraph.

For every detected wall, door, window, and room we produce:
  * a per-category schedule row (door schedule, window schedule, etc.)
  * a CSI-division classification (08-Openings, 09-Finishes, ...)
  * a list of CD sheet codes where the item should appear (A-101, A-601, ...)

The result is a ``ProjectSchedule`` Pydantic model that can be serialised to
JSON, rendered into HTML tables, or exported as CSV (one file per category).

The routing logic is config-driven (``config/cd_set.json``) so each firm /
project type can override its own sheet conventions without code changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..ingest.plan_model import (
    Fixture,
    FixtureKind,
    Opening,
    OpeningKind,
    PlanGraph,
    Room,
    Wall,
    WallStatus,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "cd_set.json"


# ---------------------------------------------------------------------------
# Schedule row models — one per CD schedule type
# ---------------------------------------------------------------------------

class DoorScheduleRow(BaseModel):
    mark: str
    width_in: float
    height_in: float
    type_: str = "Single Swing"
    material: str = "Wood"
    frame: str = "HM"               # hollow metal default
    hardware_set: str = "HW-1"
    fire_rating: str = ""
    notes: str = ""
    wall_id: str = ""
    csi_division: str = "08"
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-DOOR"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.35
    knowledge_ref: dict = Field(default_factory=dict)


class WindowScheduleRow(BaseModel):
    mark: str
    width_in: float
    height_in: float
    sill_height_in: float = 30.0
    type_: str = "Fixed"
    material: str = "Aluminum"
    glazing: str = "1\" IGU"
    notes: str = ""
    wall_id: str = ""
    csi_division: str = "08"
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-GLAZ"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.35
    knowledge_ref: dict = Field(default_factory=dict)


class RoomScheduleRow(BaseModel):
    mark: str
    name: str
    area_sqft: float
    use_: str = ""                  # building-code use
    floor: str = ""                 # finish callouts
    base: str = ""
    walls: str = ""
    ceiling: str = ""
    ceiling_height_in: float = 0.0
    notes: str = ""
    csi_division: str = "09"
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-AREA"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.13
    knowledge_ref: dict = Field(default_factory=dict)


class WallTypeScheduleRow(BaseModel):
    mark: str                       # "WT-1", "WT-2", ...
    status: str                     # "Existing" | "Demolition" | "New Construction"
    thickness_in: float
    height_in: float
    composition: str = ""
    fire_rating: str = ""
    count: int = 0                  # number of segments of this type
    total_length_ft: float = 0.0
    csi_division: str = "09"
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-WALL"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.50
    knowledge_ref: dict = Field(default_factory=dict)


class FixtureScheduleRow(BaseModel):
    """Built-in / stationary item entry — Equipment / FFE schedule."""
    mark: str                       # "F001", "F002", ...
    kind: str                       # "Casework", "Plumbing Fixture", etc.
    name: str = ""
    width_in: float = 0.0
    depth_in: float = 0.0
    height_in: float = 0.0
    will_be_removed: bool = False
    room_id: str = ""
    notes: str = ""
    csi_division: str = "11"        # Equipment by default
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-EQPM-FIXD"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.35
    knowledge_ref: dict = Field(default_factory=dict)


class FloorFinishScheduleRow(BaseModel):
    """One row per room from the perspective of floor finish."""
    room_mark: str
    room_name: str
    area_sqft: float
    finish: str                     # "LVT", "Tile", etc.
    notes: str = ""
    csi_division: str = "09"
    sheets: list[str] = Field(default_factory=list)
    aia_layer: str = "A-FLOR-PATT"
    line_type: str = "CONTINUOUS"
    lineweight_mm: float = 0.13
    knowledge_ref: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level schedule
# ---------------------------------------------------------------------------

class CSIDivisionSummary(BaseModel):
    code: str                       # "08"
    name: str                       # "Openings"
    item_count: int = 0
    item_marks: list[str] = Field(default_factory=list)


class SheetMatrixRow(BaseModel):
    """One row per (sheet_code, category) pairing."""
    sheet_code: str
    sheet_name: str
    category: str                   # "Doors", "Windows", "Rooms", "Walls"
    item_count: int
    csi_divisions: list[str]


class ProjectSchedule(BaseModel):
    project_name: str = ""
    level_name: str = ""
    doors: list[DoorScheduleRow] = Field(default_factory=list)
    windows: list[WindowScheduleRow] = Field(default_factory=list)
    rooms: list[RoomScheduleRow] = Field(default_factory=list)
    wall_types: list[WallTypeScheduleRow] = Field(default_factory=list)
    fixtures: list[FixtureScheduleRow] = Field(default_factory=list)
    floor_finishes: list[FloorFinishScheduleRow] = Field(default_factory=list)
    csi_summary: list[CSIDivisionSummary] = Field(default_factory=list)
    sheet_matrix: list[SheetMatrixRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def load_cd_config(path: Optional[Path] = None) -> dict:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path) as f:
        return json.load(f)


def _load_aia_layer_map() -> tuple[dict, dict]:
    """Return (element_to_layer, layer_name -> {color, linetype, lineweight_mm})."""
    layers_path = REPO_ROOT / "config" / "drafting" / "aia_layers.json"
    if not layers_path.exists():
        return {}, {}
    data = json.loads(layers_path.read_text())
    element_to_layer = data.get("element_to_layer", {}) or {}
    layer_props: dict = {}
    for layer in data.get("layers", []) or []:
        layer_props[layer["name"]] = {
            "color": layer.get("color"),
            "linetype": layer.get("linetype", "CONTINUOUS"),
            "lineweight_mm": layer.get("lineweight_mm", 0.35),
            "desc": layer.get("desc", ""),
        }
    return element_to_layer, layer_props


_ELEMENT_TO_LAYER, _LAYER_PROPS = _load_aia_layer_map()


def _layer_for(key: str, fallback: str) -> tuple[str, str, float]:
    layer = _ELEMENT_TO_LAYER.get(key) or fallback
    props = _LAYER_PROPS.get(layer, {})
    return (
        layer,
        props.get("linetype", "CONTINUOUS"),
        float(props.get("lineweight_mm", 0.35)),
    )


def build_schedule(
    plan: PlanGraph,
    *,
    config_path: Optional[Path] = None,
) -> ProjectSchedule:
    cfg = load_cd_config(config_path)
    routing = cfg.get("element_routing", {})
    prefixes = cfg.get("mark_prefixes", {})
    csi_names = cfg.get("csi_divisions", {})
    sheet_names = cfg.get("sheet_codes", {})

    sched = ProjectSchedule(
        project_name=plan.project_name,
        level_name=plan.level_name,
    )

    # ── Doors / Windows / Cased openings ────────────────────────────
    door_idx = window_idx = open_idx = 0
    for o in plan.openings:
        if o.kind == OpeningKind.DOOR:
            door_idx += 1
            mark = f"{prefixes.get('door', 'D')}{door_idx:03d}"
            row_cfg = routing.get("door", {})
            layer, lt, lw = _layer_for("Door", "A-DOOR")
            sched.doors.append(DoorScheduleRow(
                mark=mark,
                width_in=o.width_in,
                height_in=o.height_in,
                wall_id=o.wall_id,
                csi_division=row_cfg.get("csi_division", "08"),
                sheets=row_cfg.get("sheets", []),
                aia_layer=layer, line_type=lt, lineweight_mm=lw,
            ))
        elif o.kind == OpeningKind.WINDOW:
            window_idx += 1
            mark = f"{prefixes.get('window', 'W')}{window_idx:03d}"
            row_cfg = routing.get("window", {})
            layer, lt, lw = _layer_for("Window", "A-GLAZ")
            sched.windows.append(WindowScheduleRow(
                mark=mark,
                width_in=o.width_in,
                height_in=o.height_in,
                sill_height_in=o.sill_height_in,
                wall_id=o.wall_id,
                csi_division=row_cfg.get("csi_division", "08"),
                sheets=row_cfg.get("sheets", []),
                aia_layer=layer, line_type=lt, lineweight_mm=lw,
            ))
        else:
            open_idx += 1
            mark = f"{prefixes.get('opening_cased', 'O')}{open_idx:03d}"
            row_cfg = routing.get("opening_cased", {})
            layer, lt, lw = _layer_for("Opening", "A-DOOR-FRAM")
            # Cased openings live in the door schedule with a note.
            sched.doors.append(DoorScheduleRow(
                mark=mark,
                width_in=o.width_in,
                height_in=o.height_in,
                type_="Cased Opening",
                material="",
                frame="N/A",
                hardware_set="",
                notes="No leaf",
                wall_id=o.wall_id,
                csi_division=row_cfg.get("csi_division", "08"),
                sheets=row_cfg.get("sheets", []),
                aia_layer=layer, line_type=lt, lineweight_mm=lw,
            ))

    # ── Rooms ───────────────────────────────────────────────────────
    room_cfg = routing.get("room", {})
    floor_cfg = routing.get("floor_finish", room_cfg)
    for i, r in enumerate(plan.rooms, start=1):
        mark = f"{prefixes.get('room', 'R')}{i:03d}"
        layer, lt, lw = _layer_for("Room", "A-AREA")
        sched.rooms.append(RoomScheduleRow(
            mark=mark,
            name=r.name or "ROOM",
            area_sqft=round(r.area_sqft, 1),
            use_=r.use or "",
            floor=getattr(r, "floor_finish", "") or "",
            ceiling=getattr(r, "ceiling_finish", "") or "",
            ceiling_height_in=getattr(r, "ceiling_height_in", 0.0) or 0.0,
            csi_division=room_cfg.get("csi_division", "09"),
            sheets=room_cfg.get("sheets", []),
            aia_layer=layer, line_type=lt, lineweight_mm=lw,
        ))
        # Floor Finish Schedule entry
        finish = getattr(r, "floor_finish", "") or ""
        if finish:
            sched.floor_finishes.append(FloorFinishScheduleRow(
                room_mark=mark,
                room_name=r.name or "ROOM",
                area_sqft=round(r.area_sqft, 1),
                finish=finish,
                csi_division=floor_cfg.get("csi_division", "09"),
                sheets=floor_cfg.get("sheets", ["A-101", "A-603"]),
            ))

    # ── Fixtures (built-ins) ────────────────────────────────────────
    fixture_csi_map = {
        "Casework": "06",            # Wood/Plastic/Composites
        "Plumbing Fixture": "22",
        "Equipment": "11",
        "Appliance": "11",
        "Reception Desk": "06",
        "Exam Table": "11",
        "Kennel Run": "11",
        "Column": "05",              # Metals (or 03 Concrete)
        "Stair": "06",
        "Other Built-in": "10",      # Specialties
    }
    fixture_sheets_default = ["A-101", "A-501", "A-901"]
    for i, fx in enumerate(plan.fixtures or [], start=1):
        kind_val = fx.kind.value if hasattr(fx.kind, "value") else str(fx.kind)
        w_in = abs(fx.bbox_max.x - fx.bbox_min.x)
        d_in = abs(fx.bbox_max.y - fx.bbox_min.y)
        layer, lt, lw = _layer_for(f"Fixture|{kind_val}", "A-EQPM-FIXD")
        sched.fixtures.append(FixtureScheduleRow(
            mark=f"F{i:03d}",
            kind=kind_val,
            name=fx.name,
            width_in=round(w_in, 1),
            depth_in=round(d_in, 1),
            height_in=round(fx.height_in, 1),
            will_be_removed=fx.will_be_removed,
            room_id=fx.room_id,
            notes=fx.notes,
            csi_division=fixture_csi_map.get(kind_val, "11"),
            sheets=fixture_sheets_default,
            aia_layer=layer, line_type=lt, lineweight_mm=lw,
        ))

    # ── Wall types (group by status + rounded thickness) ────────────
    bucket: dict[tuple[str, float], WallTypeScheduleRow] = {}
    for w in plan.walls:
        key = (
            w.status.value if hasattr(w.status, "value") else str(w.status),
            round(w.thickness_in, 1),
        )
        if key not in bucket:
            status_str = key[0]
            route_key = {
                "Existing": "wall_existing",
                "Demolition": "wall_demolition",
                "New Construction": "wall_new",
            }.get(status_str, "wall_existing")
            row_cfg = routing.get(route_key, {})
            wall_layer_key = f"Wall|{status_str}"
            layer, lt, lw = _layer_for(wall_layer_key, "A-WALL")
            bucket[key] = WallTypeScheduleRow(
                mark=f"WT-{len(bucket) + 1}",
                status=status_str,
                thickness_in=key[1],
                height_in=w.height_in,
                csi_division=row_cfg.get("csi_division", "09"),
                sheets=row_cfg.get("sheets", []),
                aia_layer=layer, line_type=lt, lineweight_mm=lw,
            )
        wt = bucket[key]
        wt.count += 1
        # length in real-world inches -> feet
        import math
        length_in = math.hypot(w.end.x - w.start.x, w.end.y - w.start.y)
        wt.total_length_ft += length_in / 12.0
    sched.wall_types = list(bucket.values())
    for wt in sched.wall_types:
        wt.total_length_ft = round(wt.total_length_ft, 1)

    # ── CSI Summary ─────────────────────────────────────────────────
    by_div: dict[str, CSIDivisionSummary] = {}

    def add(div: str, mark: str):
        if not div:
            return
        if div not in by_div:
            by_div[div] = CSIDivisionSummary(code=div, name=csi_names.get(div, ""))
        by_div[div].item_count += 1
        by_div[div].item_marks.append(mark)

    for d in sched.doors:
        add(d.csi_division, d.mark)
    for w in sched.windows:
        add(w.csi_division, w.mark)
    for r in sched.rooms:
        add(r.csi_division, r.mark)
    for wt in sched.wall_types:
        for _ in range(wt.count):
            add(wt.csi_division, wt.mark)
    for fx in sched.fixtures:
        add(fx.csi_division, fx.mark)
    for ff in sched.floor_finishes:
        add(ff.csi_division, ff.room_mark)
    sched.csi_summary = sorted(by_div.values(), key=lambda x: x.code)

    # ── Sheet matrix ────────────────────────────────────────────────
    matrix: dict[tuple[str, str], SheetMatrixRow] = {}

    def place(sheet_codes: list[str], category: str, div: str):
        for sc in sheet_codes:
            k = (sc, category)
            if k not in matrix:
                matrix[k] = SheetMatrixRow(
                    sheet_code=sc,
                    sheet_name=sheet_names.get(sc, ""),
                    category=category,
                    item_count=0,
                    csi_divisions=[],
                )
            matrix[k].item_count += 1
            if div not in matrix[k].csi_divisions:
                matrix[k].csi_divisions.append(div)

    for d in sched.doors:
        place(d.sheets, "Doors", d.csi_division)
    for w in sched.windows:
        place(w.sheets, "Windows", w.csi_division)
    for r in sched.rooms:
        place(r.sheets, "Rooms", r.csi_division)
    for wt in sched.wall_types:
        for _ in range(wt.count):
            place(wt.sheets, "Walls", wt.csi_division)
    for fx in sched.fixtures:
        place(fx.sheets, "Fixtures", fx.csi_division)
    for ff in sched.floor_finishes:
        place(ff.sheets, "Floor Finishes", ff.csi_division)
    sched.sheet_matrix = sorted(matrix.values(), key=lambda x: (x.sheet_code, x.category))

    return sched
