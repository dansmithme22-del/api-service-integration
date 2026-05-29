"""Enrich a ProjectSchedule with semantic matches from the knowledge store.

For each schedule row we build a short text query, search the
``KnowledgeStore``, and attach the top hit to the row as ``knowledge_ref``.

The attached match contains enough fields for the schedule exporter to show
a per-row "what does the knowledge base say about this" callout without
re-querying.

This module is import-light: ``KnowledgeStore`` lives in ``src.knowledge``
and is only instantiated when the caller passes one in. If the DB isn't
available the caller can simply skip calling ``enrich_schedule``.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..knowledge import KnowledgeStore, SearchResult
from .scheduler import (
    DoorScheduleRow,
    FixtureScheduleRow,
    FloorFinishScheduleRow,
    ProjectSchedule,
    RoomScheduleRow,
    WallTypeScheduleRow,
    WindowScheduleRow,
)

logger = logging.getLogger(__name__)


def enrich_schedule(
    sched: ProjectSchedule,
    store: KnowledgeStore,
    *,
    permit_mode: bool = False,
    top_k: int = 1,
) -> ProjectSchedule:
    """Attach the closest knowledge-store match to each schedule row.

    Returns the same ``sched`` instance with ``knowledge_ref`` populated.

    Each match is a small dict::

        {
          "id":            "csi:08",
          "name":          "Openings",
          "layer":         "csi",
          "kind":          "csi_division",
          "code":          "08",
          "csi_division":  "08",
          "sheets":        ["A-101", "A-501", "A-601"],
          "score":         0.48,
          "all_matches":   [ ...top_k items... ]
        }
    """
    for d in sched.doors:
        q = _door_query(d)
        d.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                 preferred_divisions={"08"})
    for w in sched.windows:
        q = _window_query(w)
        w.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                 preferred_divisions={"08"})
    for r in sched.rooms:
        q = _room_query(r)
        r.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                 preferred_divisions={"09"})
    for wt in sched.wall_types:
        q = _wall_type_query(wt)
        wt.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                  preferred_divisions=_wall_preferred_divisions(wt.status))
    for fx in sched.fixtures:
        q = _fixture_query(fx)
        fx.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                  preferred_divisions=_fixture_preferred_divisions(fx.kind))
    for ff in sched.floor_finishes:
        q = _floor_finish_query(ff)
        ff.knowledge_ref = _match(store, q, top_k=top_k, permit_mode=permit_mode,
                                  preferred_divisions={"09"})

    logger.info(
        "Knowledge-enriched: %d doors, %d windows, %d rooms, %d wall-types, "
        "%d fixtures, %d floor-finishes",
        len(sched.doors), len(sched.windows), len(sched.rooms),
        len(sched.wall_types), len(sched.fixtures), len(sched.floor_finishes),
    )
    return sched


# ---------------------------------------------------------------------------
# Query builders — designed so the embedding text encodes the row's character.
# ---------------------------------------------------------------------------

def _door_query(d: DoorScheduleRow) -> str:
    bits = ["door schedule", d.type_]
    if d.fire_rating:
        bits.append(f"{d.fire_rating} fire rated")
    if d.frame:
        bits.append(f"{d.frame} frame")
    return " ".join(bits)


def _window_query(w: WindowScheduleRow) -> str:
    return f"window schedule {w.type_} {w.material} glazing {w.glazing}".strip()


def _room_query(r: RoomScheduleRow) -> str:
    bits = [r.name or "room", "finish schedule"]
    if r.floor:
        bits.append(f"{r.floor} floor")
    if r.ceiling:
        bits.append(f"{r.ceiling} ceiling")
    if r.use_:
        bits.append(f"use {r.use_}")
    return " ".join(bits)


def _wall_type_query(wt: WallTypeScheduleRow) -> str:
    bits = ["wall type schedule", wt.status]
    if wt.fire_rating:
        bits.append(f"{wt.fire_rating} rated partition")
    if wt.composition:
        bits.append(wt.composition)
    return " ".join(bits)


def _fixture_query(fx: FixtureScheduleRow) -> str:
    return f"{fx.kind} {fx.name}".strip() or "built-in fixture"


def _floor_finish_query(ff: FloorFinishScheduleRow) -> str:
    return f"floor finish {ff.finish} schedule {ff.room_name}".strip()


# ---------------------------------------------------------------------------
# Preferred-division hints
# ---------------------------------------------------------------------------

_FIXTURE_DIV_MAP = {
    "Casework": "06",
    "Reception Desk": "06",
    "Stair": "06",
    "Plumbing Fixture": "22",
    "Equipment": "11",
    "Appliance": "11",
    "Exam Table": "11",
    "Kennel Run": "11",
    "Column": "05",
    "Other Built-in": "10",
}


def _fixture_preferred_divisions(kind: str) -> set[str]:
    div = _FIXTURE_DIV_MAP.get(kind, "")
    return {div} if div else set()


def _wall_preferred_divisions(status: str) -> set[str]:
    if status == "Demolition":
        return {"02"}
    if status == "Existing":
        return {"02"}
    return {"09"}


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _match(
    store: KnowledgeStore,
    query: str,
    *,
    top_k: int,
    permit_mode: bool,
    preferred_divisions: Optional[set[str]] = None,
) -> dict:
    """Search the store and return a compact dict describing the top hit."""
    try:
        # Pull a few extras so we can re-rank by preferred division.
        results = store.search(query, k=max(top_k * 4, 4), permit_mode=permit_mode)
    except Exception as exc:
        logger.warning("Knowledge search failed for %r: %s", query, exc)
        return {}

    if not results:
        return {}

    # Re-rank: bias toward results that match a preferred CSI division.
    if preferred_divisions:
        def boost(r: SearchResult) -> float:
            if (r.item.csi_division and r.item.csi_division in preferred_divisions):
                return r.score + 0.10
            if (r.item.code and r.item.code in preferred_divisions):
                return r.score + 0.10
            return r.score
        results = sorted(results, key=boost, reverse=True)

    top = results[0]
    return {
        "id": top.item.id,
        "name": top.item.name,
        "layer": top.item.layer.value,
        "kind": top.item.kind.value,
        "code": top.item.code,
        "csi_division": top.item.csi_division,
        "sheets": top.item.sheets,
        "score": round(top.score, 3),
        "all_matches": [
            {
                "id": r.item.id,
                "name": r.item.name,
                "layer": r.item.layer.value,
                "score": round(r.score, 3),
            }
            for r in results[:top_k]
        ],
    }
