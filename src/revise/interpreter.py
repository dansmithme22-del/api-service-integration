"""Apply a natural-language revision request to a PlanGraph.

Architecture:
  1. Serialize the input PlanGraph as JSON.
  2. Send it + the revision text to Gemini with a strict JSON schema asking
     for a list of structured ops: add_wall, remove_wall, modify_wall,
     add_opening, remove_opening, etc.
  3. Apply the ops to a copy of the PlanGraph; record each in a ChangeLog.
  4. Return (new_plan, changelog).

This module is intentionally narrow: it does NOT touch Archicad. The result
is fed back through the build/ layer like a fresh PlanGraph.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from ..ingest.plan_model import (
    Opening,
    OpeningKind,
    PlanGraph,
    Point,
    Wall,
    WallStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ChangeLog
# ---------------------------------------------------------------------------

@dataclass
class ChangeEntry:
    op: str                          # "add_wall", "remove_wall", etc.
    target_id: str                   # id of the affected element (or "" for adds)
    detail: str                      # human-readable summary
    payload: dict = field(default_factory=dict)


@dataclass
class ChangeLog:
    entries: list[ChangeEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, op: str, target_id: str, detail: str, **payload) -> None:
        self.entries.append(ChangeEntry(op=op, target_id=target_id, detail=detail, payload=payload))


# ---------------------------------------------------------------------------
# Gemini op schema (Pydantic for type-safety)
# ---------------------------------------------------------------------------

class _OpAddWall(BaseModel):
    op: Literal["add_wall"]
    x0_in: float
    y0_in: float
    x1_in: float
    y1_in: float
    thickness_in: float = 4.5
    status: Literal["Existing", "Demolition", "New Construction"] = "New Construction"


class _OpRemoveWall(BaseModel):
    op: Literal["remove_wall"]
    wall_id: str


class _OpMarkDemo(BaseModel):
    op: Literal["mark_demo"]
    wall_id: str


class _OpAddOpening(BaseModel):
    op: Literal["add_opening"]
    wall_id: str
    distance_along_wall_in: float
    width_in: float = 36.0
    kind: Literal["Door", "Window", "Opening"] = "Door"


class _OpRemoveOpening(BaseModel):
    op: Literal["remove_opening"]
    opening_id: str


class _OpRenameRoom(BaseModel):
    op: Literal["rename_room"]
    room_id: str
    new_name: str


_OP_TYPES = (
    _OpAddWall, _OpRemoveWall, _OpMarkDemo,
    _OpAddOpening, _OpRemoveOpening, _OpRenameRoom,
)


SYSTEM_PROMPT = """\
You are a precise architectural-revision interpreter. The user provides:
  (1) a JSON PlanGraph describing an existing floor plan
  (2) a natural-language list of revision requests

Return ONLY a JSON object: {"ops": [ ... ]}. Each op is one of:

  {"op": "add_wall",      "x0_in": float, "y0_in": float, "x1_in": float, "y1_in": float, "thickness_in": float, "status": "New Construction"}
  {"op": "remove_wall",   "wall_id": "<id from PlanGraph>"}
  {"op": "mark_demo",     "wall_id": "<id>"}     // changes status to Demolition (keeps geometry)
  {"op": "add_opening",   "wall_id": "<id>", "distance_along_wall_in": float, "width_in": float, "kind": "Door"|"Window"|"Opening"}
  {"op": "remove_opening","opening_id": "<id>"}
  {"op": "rename_room",   "room_id": "<id>", "new_name": "..."}

Rules:
  - Never change geometry the user didn't ask about.
  - Use existing wall_ids and opening_ids from the provided PlanGraph.
  - Use real-world inches; origin matches the PlanGraph (bottom-left).
  - Output JSON only — no prose, no markdown fences.
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def apply_revision_request(
    plan: PlanGraph,
    revision_text: str,
    *,
    model: str = "gemini-2.5-pro",
) -> tuple[PlanGraph, ChangeLog]:
    """Return (new_plan, changelog) after applying revision_text to plan."""
    ops = _ask_gemini_for_ops(plan, revision_text, model=model)

    new_plan = deepcopy(plan)
    log = ChangeLog()
    for op_dict in ops:
        try:
            _apply_op(new_plan, op_dict, log)
        except Exception as exc:
            log.notes.append(f"Skipped op {op_dict}: {exc}")
            logger.warning("Skip op %s: %s", op_dict, exc)

    return new_plan, log


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _ask_gemini_for_ops(plan: PlanGraph, revision_text: str, *, model: str) -> list[dict]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError("google-genai required: pip install google-genai") from exc

    client = genai.Client(api_key=api_key)
    payload = {
        "plan": json.loads(plan.model_dump_json()),
        "revision_request": revision_text,
    }
    contents = [json.dumps(payload, default=str)]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        temperature=0.1,
    )
    resp = client.models.generate_content(model=model, contents=contents, config=config)
    text = (resp.text or "").strip()
    if not text:
        return []
    parsed = json.loads(text)
    ops = parsed.get("ops") or []
    if not isinstance(ops, list):
        raise ValueError("Gemini response 'ops' is not a list")
    return ops


def _apply_op(plan: PlanGraph, op_dict: dict, log: ChangeLog) -> None:
    op = op_dict.get("op")
    if op == "add_wall":
        m = _OpAddWall.model_validate(op_dict)
        wall = Wall(
            id=f"w-{uuid.uuid4().hex[:8]}",
            start=Point(x=m.x0_in, y=m.y0_in),
            end=Point(x=m.x1_in, y=m.y1_in),
            thickness_in=m.thickness_in,
            status={
                "Existing": WallStatus.EXISTING,
                "Demolition": WallStatus.DEMOLITION,
                "New Construction": WallStatus.NEW,
            }[m.status],
            confidence=1.0,
            source_note="revision",
        )
        plan.walls.append(wall)
        log.add("add_wall", wall.id, f"Add wall {wall.start.as_tuple()} -> {wall.end.as_tuple()}", **op_dict)

    elif op == "remove_wall":
        m = _OpRemoveWall.model_validate(op_dict)
        before = len(plan.walls)
        plan.walls = [w for w in plan.walls if w.id != m.wall_id]
        if len(plan.walls) < before:
            log.add("remove_wall", m.wall_id, f"Remove wall {m.wall_id}", **op_dict)
        else:
            log.notes.append(f"remove_wall: wall_id {m.wall_id} not found")

    elif op == "mark_demo":
        m = _OpMarkDemo.model_validate(op_dict)
        found = next((w for w in plan.walls if w.id == m.wall_id), None)
        if found:
            found.status = WallStatus.DEMOLITION
            log.add("mark_demo", m.wall_id, f"Mark {m.wall_id} as demolition", **op_dict)
        else:
            log.notes.append(f"mark_demo: wall_id {m.wall_id} not found")

    elif op == "add_opening":
        m = _OpAddOpening.model_validate(op_dict)
        opening = Opening(
            id=f"o-{uuid.uuid4().hex[:8]}",
            wall_id=m.wall_id,
            distance_along_wall_in=m.distance_along_wall_in,
            width_in=m.width_in,
            kind=OpeningKind(m.kind),
            confidence=1.0,
        )
        plan.openings.append(opening)
        log.add("add_opening", opening.id, f"Add {m.kind} on wall {m.wall_id}", **op_dict)

    elif op == "remove_opening":
        m = _OpRemoveOpening.model_validate(op_dict)
        before = len(plan.openings)
        plan.openings = [o for o in plan.openings if o.id != m.opening_id]
        if len(plan.openings) < before:
            log.add("remove_opening", m.opening_id, f"Remove opening {m.opening_id}", **op_dict)
        else:
            log.notes.append(f"remove_opening: opening_id {m.opening_id} not found")

    elif op == "rename_room":
        m = _OpRenameRoom.model_validate(op_dict)
        found = next((r for r in plan.rooms if r.id == m.room_id), None)
        if found:
            old = found.name
            found.name = m.new_name
            log.add("rename_room", m.room_id, f"Rename room '{old}' -> '{m.new_name}'", **op_dict)
        else:
            log.notes.append(f"rename_room: room_id {m.room_id} not found")

    else:
        log.notes.append(f"unknown op: {op}")
