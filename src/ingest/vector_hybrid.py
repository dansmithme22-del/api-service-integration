"""Vector + Vision hybrid (the right one).

Architecture — each tool does what it's good at:

  • **Vector pipeline** (deterministic, no AI) produces clean wall
    geometry: dedupe → snap → merge → pair → centerlines.
    No room enclosure detection — we know the centerlines aren't
    connected enough for that on most real PDFs.

  • **Claude vision** produces room polygons, fixture bboxes, opening
    positions — semantic content. Claude is not asked to place
    millimetre-accurate walls; he is asked to identify what's a
    Reception and what's an Exam Room.

  • **Snap-to-walls** post-processing aligns Claude's room vertices to
    the nearest real vector wall endpoint. This combines geometric
    truth (vector) with semantic labeling (Claude).

  • **Door arcs** from the PDF curves are converted to ``Opening`` rows
    snapped to the nearest vector wall. Claude's openings are kept
    only where the arc detector finds no door.

This module replaces both the old ``hybrid.py`` (which used Claude for
everything) and the ``vector_truth.py`` first attempt at full planar
graph enumeration (which fails when walls aren't connected).
"""

from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path
from typing import Optional

from .accuracy_checker import check_plan_accuracy
from .geometry import clean_pipeline, detect_door_arcs
from .geometry.arc_detector import snap_arc_to_wall
from .plan_model import (
    Fixture,
    IngestSource,
    Opening,
    OpeningKind,
    PageMeta,
    PlanGraph,
    Point,
    Room,
    Wall,
    WallStatus,
)
from .vector_anchor import (
    NormLine,
    extract_vector_norm,
    pair_walls_norm,
)
from .vector_parser import parse_vector_page
from .vision_parser import VisionConfig

logger = logging.getLogger(__name__)


def vector_hybrid_ingest(
    pdf_path: str | Path,
    page_index: int,
    *,
    project_name: str = "",
    level_name: str = "Level 1",
    vision_config: Optional[VisionConfig] = None,
    min_wall_length_norm: float = 0.015,
    pair_max_sep_norm: float = 0.006,
    min_line_width_pt: float = 0.36,
    snap_tol_norm: float = 0.001,
    inches_per_norm_override: Optional[float] = None,
    room_snap_tolerance_in: float = 24.0,    # snap Claude vertex within 24"
) -> PlanGraph:
    """Vector geometry + AI semantics.

    Walls and door positions come from the PDF; room polygons and
    fixture / opening labels come from Claude. Coordinates anchored to
    a single calibration so both layers align.
    """
    pdf_path = Path(pdf_path)
    cfg = vision_config or VisionConfig()

    # ── Stage 1: clean vector geometry.
    vec_page = extract_vector_norm(
        pdf_path,
        page_index,
        dpi=cfg.image_dpi,
        min_line_width_pt=min_line_width_pt,
    )
    raw_page = parse_vector_page(pdf_path, page_index)
    cleaned = clean_pipeline(
        vec_page.lines,
        snap_tol=snap_tol_norm,
        angle_tol_deg=1.5,
    )
    vec_page.lines = cleaned

    pairs = pair_walls_norm(
        vec_page,
        min_wall_len_norm=min_wall_length_norm,
        pair_max_sep_norm=pair_max_sep_norm,
    )

    # ── Stage 2: vision parse for semantic content.
    from .vision_parser import (
        SYSTEM_PROMPT,
        _dict_to_plan_graph,
        _extract_json,
        _provider_for,
        _render_pdf_page_to_png,
    )

    png_bytes = _render_pdf_page_to_png(pdf_path, page_index, dpi=cfg.image_dpi)
    provider = _provider_for(cfg)
    raw_json = provider.parse_plan(
        png_bytes,
        system_prompt=SYSTEM_PROMPT,
        max_output_tokens=32768,
        temperature=0.1,
    )
    vision_plan = _dict_to_plan_graph(
        _extract_json(raw_json),
        pdf_path=str(pdf_path),
        page_index=page_index,
        project_name=project_name,
        level_name_default=level_name,
    )

    # ── Stage 3: resolve calibration.
    inches_per_norm = (
        inches_per_norm_override
        or (vision_plan.page.inches_per_norm if vision_plan.page else 0.0)
        or _default_inches_per_norm(vec_page)
    )

    # ── Stage 4: build vector walls in inches with that calibration.
    walls = _walls_from_pairs(pairs, inches_per_norm)

    # ── Stage 5: re-anchor Claude's rooms to the SAME calibration.
    # The vision parser already produced room polygons in inches at its
    # own calibration; we need to re-scale them to OUR calibration.
    claude_in_per_norm = (vision_plan.page.inches_per_norm
                          if vision_plan.page else inches_per_norm)
    scale_correction = inches_per_norm / max(claude_in_per_norm, 1e-9)

    rescaled_rooms: list[Room] = []
    for r in vision_plan.rooms:
        new_poly = [
            Point(x=p.x * scale_correction, y=p.y * scale_correction)
            for p in r.polygon
        ]
        rescaled_rooms.append(Room(
            id=r.id,
            name=r.name,
            polygon=new_poly,
            area_sqft=_polygon_area_sqft(new_poly),
            floor_finish=r.floor_finish,
            ceiling_finish=r.ceiling_finish,
            ceiling_height_in=r.ceiling_height_in,
            confidence=r.confidence,
        ))

    # ── Stage 6: snap each room vertex to nearest wall endpoint (or wall).
    snapped_rooms = _snap_rooms_to_walls(
        rescaled_rooms, walls, tolerance_in=room_snap_tolerance_in,
    )

    # ── Stage 7: detect door arcs from PDF curves; snap to walls.
    door_arcs = detect_door_arcs(
        raw_page.arcs,
        min_door_width_in=24.0,
        max_door_width_in=48.0,
        inches_per_norm=inches_per_norm,
    )
    openings = _openings_from_door_arcs(door_arcs, walls, inches_per_norm)

    # If door arc detection found nothing, fall back to Claude's openings
    # rescaled the same way and snapped to vector walls.
    if not openings and vision_plan.openings:
        for o in vision_plan.openings:
            # Recover original wall position and rescale.
            parent = next((w for w in vision_plan.walls if w.id == o.wall_id), None)
            if parent is None:
                continue
            dx = (parent.end.x - parent.start.x)
            dy = (parent.end.y - parent.start.y)
            ln = math.hypot(dx, dy) or 1.0
            t = max(0.0, min(1.0, o.distance_along_wall_in / ln))
            opx = (parent.start.x + t * dx) * scale_correction
            opy = (parent.start.y + t * dy) * scale_correction
            wall_id, dist_in = _attach_point_to_wall(opx, opy, walls)
            if not wall_id:
                continue
            openings.append(Opening(
                id=f"o-{uuid.uuid4().hex[:8]}",
                wall_id=wall_id,
                distance_along_wall_in=dist_in,
                width_in=o.width_in * scale_correction,
                sill_height_in=o.sill_height_in,
                kind=o.kind,
                swing_direction=o.swing_direction,
                confidence=0.7,
            ))

    # ── Stage 8: rescale fixtures the same way as rooms.
    rescaled_fixtures: list[Fixture] = []
    for fx in vision_plan.fixtures:
        rescaled_fixtures.append(Fixture(
            id=fx.id,
            kind=fx.kind,
            name=fx.name,
            bbox_min=Point(x=fx.bbox_min.x * scale_correction,
                           y=fx.bbox_min.y * scale_correction),
            bbox_max=Point(x=fx.bbox_max.x * scale_correction,
                           y=fx.bbox_max.y * scale_correction),
            rotation_deg=fx.rotation_deg,
            height_in=fx.height_in,
            room_id=fx.room_id,
            will_be_removed=fx.will_be_removed,
            notes=fx.notes,
            confidence=fx.confidence,
        ))

    plan = PlanGraph(
        project_name=project_name,
        level_name=level_name,
        units="imperial",
        source=IngestSource.HYBRID,
        page=PageMeta(
            page_index=page_index,
            source_pdf=str(pdf_path),
            width_in=vec_page.width_pt * (48.0 / 72.0),
            height_in=vec_page.height_pt * (48.0 / 72.0),
            detected_scale_text=(
                "1/4\" = 1'-0\" (default)" if inches_per_norm_override is None
                else f"override {inches_per_norm_override:.2f} in/norm"
            ),
            is_vector=True,
            confidence=0.9,
            drawing_area_norm_bbox=(vision_plan.page.drawing_area_norm_bbox
                                    if vision_plan.page else None),
            image_width_px=vec_page.image_width_px,
            image_height_px=vec_page.image_height_px,
            inches_per_norm=inches_per_norm,
            geom_norm_bbox=_walls_norm_bbox(pairs),
            calibration_dim_text=(vision_plan.page.calibration_dim_text
                                  if vision_plan.page else ""),
            calibration_dim_in=(vision_plan.page.calibration_dim_in
                                if vision_plan.page else 0.0),
        ),
        walls=walls,
        openings=openings,
        rooms=snapped_rooms,
        fixtures=rescaled_fixtures,
        annotations=vision_plan.annotations,
        dimension_callouts=vision_plan.dimension_callouts,
        warnings=list(vision_plan.warnings),
    )

    check_plan_accuracy(plan)

    logger.info(
        "Vector-hybrid: %d walls (vector), %d rooms (Claude snapped), "
        "%d openings (%d from arcs), %d fixtures",
        len(plan.walls), len(plan.rooms), len(plan.openings),
        sum(1 for o in plan.openings if o.confidence > 0.9),
        len(plan.fixtures),
    )
    return plan


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _default_inches_per_norm(vec_page) -> float:
    long_pt = max(vec_page.width_pt, vec_page.height_pt)
    return long_pt * (48.0 / 72.0)


def _walls_from_pairs(
    pairs: list[tuple[NormLine, NormLine]],
    inches_per_norm: float,
) -> list[Wall]:
    walls: list[Wall] = []
    for a, b in pairs:
        cx0n = (a.x0 + b.x0) / 2.0
        cy0n = (a.y0 + b.y0) / 2.0
        cx1n = (a.x1 + b.x1) / 2.0
        cy1n = (a.y1 + b.y1) / 2.0
        sx = cx0n * inches_per_norm
        sy = (1.0 - cy0n) * inches_per_norm
        ex = cx1n * inches_per_norm
        ey = (1.0 - cy1n) * inches_per_norm
        thickness_in = max(2.5, min(14.0,
                                     _perp_distance(a, b) * inches_per_norm))
        walls.append(Wall(
            id=f"w-{uuid.uuid4().hex[:8]}",
            start=Point(x=sx, y=sy),
            end=Point(x=ex, y=ey),
            thickness_in=thickness_in,
            height_in=108.0,
            status=WallStatus.EXISTING,
            confidence=0.95,
            source_note="vector",
        ))
    return walls


def _walls_norm_bbox(pairs):
    if not pairs:
        return None
    xs, ys = [], []
    for a, b in pairs:
        xs.extend([a.x0, a.x1, b.x0, b.x1])
        ys.extend([a.y0, a.y1, b.y0, b.y1])
    return [min(xs), min(ys), max(xs), max(ys)]


def _perp_distance(a, b) -> float:
    avx, avy = a.x1 - a.x0, a.y1 - a.y0
    a_len = math.hypot(avx, avy)
    if a_len < 1e-9:
        return 0.0
    nx, ny = -avy / a_len, avx / a_len
    d0 = abs((b.x0 - a.x0) * nx + (b.y0 - a.y0) * ny)
    d1 = abs((b.x1 - a.x0) * nx + (b.y1 - a.y0) * ny)
    return (d0 + d1) / 2.0


def _polygon_area_sqft(polygon: list[Point]) -> float:
    n = len(polygon)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = polygon[i].x, polygon[i].y
        x1, y1 = polygon[(i + 1) % n].x, polygon[(i + 1) % n].y
        s += x0 * y1 - x1 * y0
    return round(abs(s) / 2.0 / 144.0, 1)


# ---------------------------------------------------------------------------
# Snap rooms to walls
# ---------------------------------------------------------------------------

def _snap_rooms_to_walls(
    rooms: list[Room],
    walls: list[Wall],
    *,
    tolerance_in: float,
) -> list[Room]:
    """For each room vertex, snap to the nearest wall endpoint or wall point.

    Two-pass: first try to snap each vertex to a wall ENDPOINT (those are
    real building corners). Anything not snapped to an endpoint is then
    snapped to the closest point on the closest wall segment.
    """
    if not walls:
        return rooms

    # Collect all wall endpoints.
    endpoints = []
    for w in walls:
        endpoints.append((w.start.x, w.start.y))
        endpoints.append((w.end.x, w.end.y))

    snapped: list[Room] = []
    for r in rooms:
        new_poly: list[Point] = []
        for p in r.polygon:
            # Pass 1: nearest endpoint within tolerance
            best_d = math.inf
            best = (p.x, p.y)
            for (ex, ey) in endpoints:
                d = math.hypot(p.x - ex, p.y - ey)
                if d < best_d and d <= tolerance_in:
                    best_d = d
                    best = (ex, ey)
            if best_d < tolerance_in:
                new_poly.append(Point(x=best[0], y=best[1]))
                continue
            # Pass 2: nearest point on a wall segment within larger tolerance
            best_d = math.inf
            best = (p.x, p.y)
            seg_tol = tolerance_in * 1.5
            for w in walls:
                ax, ay = w.start.x, w.start.y
                bx, by = w.end.x, w.end.y
                wx, wy = bx - ax, by - ay
                wlen_sq = wx * wx + wy * wy
                if wlen_sq < 1e-9:
                    continue
                t = max(0.0, min(1.0, ((p.x - ax) * wx + (p.y - ay) * wy) / wlen_sq))
                px = ax + t * wx
                py = ay + t * wy
                d = math.hypot(p.x - px, p.y - py)
                if d < best_d and d <= seg_tol:
                    best_d = d
                    best = (px, py)
            if best_d <= seg_tol:
                new_poly.append(Point(x=best[0], y=best[1]))
            else:
                new_poly.append(p)
        # Drop degenerate vertices (adjacent same point) introduced by snap.
        deduped: list[Point] = []
        for p in new_poly:
            if not deduped or math.hypot(p.x - deduped[-1].x, p.y - deduped[-1].y) > 1.0:
                deduped.append(p)
        snapped.append(Room(
            id=r.id,
            name=r.name,
            polygon=deduped,
            area_sqft=_polygon_area_sqft(deduped),
            floor_finish=r.floor_finish,
            ceiling_finish=r.ceiling_finish,
            ceiling_height_in=r.ceiling_height_in,
            confidence=r.confidence * 0.9,
        ))
    logger.info(
        "Snapped %d rooms to %d vector walls (tol=%.1f in)",
        len(snapped), len(walls), tolerance_in,
    )
    return snapped


# ---------------------------------------------------------------------------
# Door arcs → Opening
# ---------------------------------------------------------------------------

def _openings_from_door_arcs(
    door_arcs,
    walls: list[Wall],
    inches_per_norm: float,
) -> list[Opening]:
    class _WP:
        __slots__ = ("id", "start", "end")

    proxies = []
    for w in walls:
        p = _WP()
        p.id = w.id
        sx = w.start.x / inches_per_norm
        sy = 1.0 - w.start.y / inches_per_norm
        ex = w.end.x / inches_per_norm
        ey = 1.0 - w.end.y / inches_per_norm
        p.start = type("PT", (), {"x": sx, "y": sy})()
        p.end = type("PT", (), {"x": ex, "y": ey})()
        proxies.append(p)

    openings: list[Opening] = []
    for arc in door_arcs:
        wall_id, dist_norm = snap_arc_to_wall(arc, proxies, max_snap_norm=0.015)
        if not wall_id:
            continue
        openings.append(Opening(
            id=f"o-{uuid.uuid4().hex[:8]}",
            wall_id=wall_id,
            distance_along_wall_in=dist_norm * inches_per_norm,
            width_in=arc.radius_norm * inches_per_norm,
            height_in=80.0,
            sill_height_in=0.0,
            kind=OpeningKind.DOOR,
            confidence=0.95,
        ))
    return openings


def _attach_point_to_wall(
    x: float, y: float, walls: list[Wall],
) -> tuple[str, float]:
    best_id = ""
    best_dist = math.inf
    best_t = 0.0
    for w in walls:
        ax, ay = w.start.x, w.start.y
        bx, by = w.end.x, w.end.y
        wx, wy = bx - ax, by - ay
        wlen_sq = wx * wx + wy * wy
        if wlen_sq < 1e-9:
            continue
        t = max(0.0, min(1.0, ((x - ax) * wx + (y - ay) * wy) / wlen_sq))
        px = ax + t * wx
        py = ay + t * wy
        d = math.hypot(x - px, y - py)
        if d < best_dist:
            best_dist = d
            best_id = w.id
            best_t = t * math.sqrt(wlen_sq)
    return best_id, best_t
