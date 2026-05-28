"""Vector-truth ingest: read the PDF as CAD data, not as an image.

Pipeline (per `agent_docs/130_DRAFTING_STANDARDS.md`):

  Stage 1 — Vector extraction       (vector_anchor.extract_vector_norm)
  Stage 2 — Clean walls              (geometry.snap)
  Stage 3 — Pair walls into pairs    (vector_anchor.pair_walls_norm)
  Stage 4 — Planar graph + faces     (geometry.planar_graph)
  Stage 5 — Door arc detection       (geometry.arc_detector)
  Stage 6 — Optional Claude labeling (vision_parser for room names)
  Stage 7 — Calibrate inches/norm    (from a dim callout if available,
                                       otherwise default 1/4" = 1'-0")

The output PlanGraph has:
  * walls   — from real PDF linework (after dedupe + snap + merge + pair)
  * rooms   — from planar-graph face enumeration; areas are exact
  * openings — from door arc geometry, snapped to nearest wall
  * fixtures — only what Claude reports (Claude is good at semantic
               labels even when geometry is wrong; we keep his bbox
               estimates labelled as confidence < 0.7)
  * dimension_callouts — TODO: extract from PDF text when available

For vector PDFs this path replaces the hybrid AI pipeline. The hybrid
pipeline (vision-guided) stays as the fallback for raster / scanned
PDFs that don't have extractable vector geometry.
"""

from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path
from typing import Optional

from .accuracy_checker import check_plan_accuracy
from .geometry import (
    build_planar_graph,
    clean_pipeline,
    detect_door_arcs,
    enumerate_faces,
)
from .geometry.arc_detector import snap_arc_to_wall
from .plan_model import (
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def vector_truth_ingest(
    pdf_path: str | Path,
    page_index: int,
    *,
    project_name: str = "",
    level_name: str = "Level 1",
    inches_per_norm_override: Optional[float] = None,
    min_wall_length_norm: float = 0.012,
    pair_max_sep_norm: float = 0.015,
    min_line_width_pt: float = 0.36,
    snap_tol_norm: float = 0.0018,
    min_room_area_ratio: float = 0.0005,   # below this, treat face as noise
) -> PlanGraph:
    """Build a PlanGraph from the PDF's vector geometry directly.

    No vision-model dependency. Coordinates are anchored to the PDF
    user-space (which is exact) and converted to inches via either an
    explicit override or the default 1/4" = 1'-0" scale.
    """
    pdf_path = Path(pdf_path)

    # ── Stage 1: extract raw vector linework + arcs in image-norm coords.
    vec_page = extract_vector_norm(
        pdf_path,
        page_index,
        dpi=200,
        min_line_width_pt=min_line_width_pt,
    )
    raw_page = parse_vector_page(pdf_path, page_index)
    arcs = raw_page.arcs

    # ── Stage 2: clean walls (dedupe + snap + merge collinear).
    cleaned = clean_pipeline(
        vec_page.lines,
        snap_tol=snap_tol_norm,
        angle_tol_deg=1.5,
    )

    # ── Stage 3: pair lines into wall centerlines.
    pairs = pair_walls_norm(
        type(vec_page)(
            page_index=vec_page.page_index,
            width_pt=vec_page.width_pt,
            height_pt=vec_page.height_pt,
            image_width_px=vec_page.image_width_px,
            image_height_px=vec_page.image_height_px,
            lines=cleaned,
        ),
        min_wall_len_norm=min_wall_length_norm,
        pair_max_sep_norm=pair_max_sep_norm,
    )

    # ── Stage 7 (calibration first so we can build walls in inches):
    inches_per_norm = inches_per_norm_override or _default_inches_per_norm(vec_page)

    # ── Build wall centerlines in inches.
    walls = _walls_from_pairs(pairs, inches_per_norm)

    # ── Stage 4: planar graph + face enumeration → rooms.
    # Centerlines must be EXTENDED slightly so they meet at corners; the
    # raw vector pairs give centerlines that stop short of the actual
    # building corner by ~half a wall thickness. We extend by the median
    # wall thickness + a small buffer so adjacent walls share an
    # endpoint after intersection splitting.
    import statistics as _st
    med_thick_in = _st.median([w.thickness_in for w in walls]) if walls else 6.0
    extend_in = med_thick_in * 1.0
    extend_norm = extend_in / inches_per_norm
    centerlines = [
        _wall_to_norm_line_extended(w, inches_per_norm, extend_norm)
        for w in walls
    ]
    # Planar graph snap tolerance: anything within half median wall
    # thickness in image-norm should collapse to the same vertex.
    planar_snap = max(snap_tol_norm * 1.5, (med_thick_in / inches_per_norm) * 0.5)
    graph = build_planar_graph(centerlines, snap_tol=planar_snap)
    faces = enumerate_faces(graph)
    rooms = _rooms_from_faces(
        faces,
        inches_per_norm=inches_per_norm,
        min_area_ratio=min_room_area_ratio,
    )

    # ── Stage 5: door arc detection.
    door_arcs = detect_door_arcs(
        arcs,
        min_door_width_in=24.0,
        max_door_width_in=48.0,
        inches_per_norm=inches_per_norm,
    )
    openings = _openings_from_door_arcs(door_arcs, walls, inches_per_norm)

    plan = PlanGraph(
        project_name=project_name,
        level_name=level_name,
        units="imperial",
        source=IngestSource.VECTOR,
        page=PageMeta(
            page_index=page_index,
            source_pdf=str(pdf_path),
            width_in=vec_page.width_pt * inches_per_norm / max(vec_page.width_pt, vec_page.height_pt),
            height_in=vec_page.height_pt * inches_per_norm / max(vec_page.width_pt, vec_page.height_pt),
            detected_scale_text=("default 1/4\" = 1'-0\"" if inches_per_norm_override is None
                                  else f"override {inches_per_norm_override:.2f} in/norm"),
            is_vector=True,
            confidence=0.85,
            image_width_px=vec_page.image_width_px,
            image_height_px=vec_page.image_height_px,
            inches_per_norm=inches_per_norm,
            geom_norm_bbox=_walls_norm_bbox(pairs),
        ),
        walls=walls,
        openings=openings,
        rooms=rooms,
    )
    plan.warnings.append(
        "Vector-truth ingest: room names and use-codes not assigned. "
        "Use the AI labelling pass to attach semantic names if needed."
    )

    # Run accuracy report (will be 'unknown' since we don't extract dim callouts yet).
    check_plan_accuracy(plan)

    logger.info(
        "Vector-truth: %d walls, %d rooms, %d openings (in/norm=%.2f)",
        len(plan.walls), len(plan.rooms), len(plan.openings), inches_per_norm,
    )
    return plan


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _default_inches_per_norm(vec_page) -> float:
    """Fallback scale: assume 1/4\" = 1'-0\" applied to whichever long axis.

    Page is ``width_pt × height_pt`` points (1 pt = 1/72 inch). At
    1/4" = 1'-0" scale, every paper-inch represents 48 real-world inches.
    Image-norm 1.0 covers the long axis of the page, so::

        inches_per_norm  = (long_page_pt / 72) * 48
                         = long_page_pt * 48 / 72
                         = long_page_pt * (2/3)
    """
    long_pt = max(vec_page.width_pt, vec_page.height_pt)
    in_per_norm = long_pt * (48.0 / 72.0)
    logger.info("Default calibration: %.2f in/norm (1/4\" = 1'-0\")", in_per_norm)
    return in_per_norm


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
        sy = (1.0 - cy0n) * inches_per_norm     # Y-flip to bottom-left
        ex = cx1n * inches_per_norm
        ey = (1.0 - cy1n) * inches_per_norm
        sep_n = _perp_distance(a, b)
        thickness_in = max(2.5, min(14.0, sep_n * inches_per_norm))
        walls.append(Wall(
            id=f"w-{uuid.uuid4().hex[:8]}",
            start=Point(x=sx, y=sy),
            end=Point(x=ex, y=ey),
            thickness_in=thickness_in,
            height_in=108.0,
            status=WallStatus.EXISTING,
            confidence=0.95,
            source_note="vector_truth",
        ))
    return walls


def _wall_to_norm_line(w: Wall, inches_per_norm: float) -> NormLine:
    """Convert a wall (inches, BL origin) back to a NormLine (norm, TL origin)."""
    sx = w.start.x / inches_per_norm
    sy = 1.0 - w.start.y / inches_per_norm
    ex = w.end.x / inches_per_norm
    ey = 1.0 - w.end.y / inches_per_norm
    return NormLine(x0=sx, y0=sy, x1=ex, y1=ey, width_norm=0.0)


def _wall_to_norm_line_extended(w: Wall, inches_per_norm: float,
                                  extend_norm: float) -> NormLine:
    """Convert wall to NormLine, extended by ``extend_norm`` on both ends.

    Extension lets adjacent wall centerlines meet at the actual building
    corner instead of stopping half a wall thickness short.
    """
    sx = w.start.x / inches_per_norm
    sy = 1.0 - w.start.y / inches_per_norm
    ex = w.end.x / inches_per_norm
    ey = 1.0 - w.end.y / inches_per_norm
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return NormLine(x0=sx, y0=sy, x1=ex, y1=ey, width_norm=0.0)
    ux, uy = dx / length, dy / length
    return NormLine(
        x0=sx - ux * extend_norm, y0=sy - uy * extend_norm,
        x1=ex + ux * extend_norm, y1=ey + uy * extend_norm,
        width_norm=0.0,
    )


def _rooms_from_faces(
    faces: list,
    *,
    inches_per_norm: float,
    min_area_ratio: float,
) -> list[Room]:
    """Convert interior planar faces into Room objects.

    ``min_area_ratio`` filters out tiny noise faces (less than X of the
    total image area). The outer face is dropped.
    """
    rooms: list[Room] = []
    for face in faces:
        if face.is_outer:
            continue
        if abs(face.area) < min_area_ratio:
            continue
        # Convert each polygon point: norm (TL origin) → inches (BL origin).
        poly_inches: list[Point] = []
        for (nx, ny) in face.polygon:
            xi = nx * inches_per_norm
            yi = (1.0 - ny) * inches_per_norm
            poly_inches.append(Point(x=xi, y=yi))

        # Polygon area in real-world inches²; convert to sq ft.
        area_in2 = abs(_polygon_area_inches(poly_inches))
        area_sqft = area_in2 / 144.0
        if area_sqft < 4.0:        # < 4 sq ft is noise
            continue
        rooms.append(Room(
            id=f"r-{uuid.uuid4().hex[:8]}",
            name="ROOM",
            polygon=poly_inches,
            area_sqft=round(area_sqft, 1),
            confidence=0.9,
        ))
    rooms.sort(key=lambda r: -r.area_sqft)
    return rooms


def _polygon_area_inches(polygon: list[Point]) -> float:
    n = len(polygon)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = polygon[i].x, polygon[i].y
        x1, y1 = polygon[(i + 1) % n].x, polygon[(i + 1) % n].y
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _walls_norm_bbox(
    pairs: list[tuple[NormLine, NormLine]],
) -> Optional[list[float]]:
    if not pairs:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for a, b in pairs:
        xs.extend([a.x0, a.x1, b.x0, b.x1])
        ys.extend([a.y0, a.y1, b.y0, b.y1])
    return [min(xs), min(ys), max(xs), max(ys)]


def _perp_distance(a: NormLine, b: NormLine) -> float:
    avx, avy = a.x1 - a.x0, a.y1 - a.y0
    a_len = math.hypot(avx, avy)
    if a_len < 1e-9:
        return 0.0
    nx, ny = -avy / a_len, avx / a_len
    d0 = abs((b.x0 - a.x0) * nx + (b.y0 - a.y0) * ny)
    d1 = abs((b.x1 - a.x0) * nx + (b.y1 - a.y0) * ny)
    return (d0 + d1) / 2.0


def _openings_from_door_arcs(
    door_arcs: list,
    walls: list[Wall],
    inches_per_norm: float,
) -> list[Opening]:
    """Snap each door-swing arc to its nearest wall and emit an Opening."""
    # Convert walls to a list of norm-line proxies for snap_arc_to_wall.
    class _WP:
        __slots__ = ("id", "start", "end")
    proxies = []
    for w in walls:
        p = _WP()
        p.id = w.id
        # snap_arc_to_wall expects (.x, .y) attrs in image-norm
        sx = w.start.x / inches_per_norm
        sy = 1.0 - w.start.y / inches_per_norm
        ex = w.end.x / inches_per_norm
        ey = 1.0 - w.end.y / inches_per_norm
        p.start = type("PT", (), {"x": sx, "y": sy})()
        p.end = type("PT", (), {"x": ex, "y": ey})()
        proxies.append(p)

    openings: list[Opening] = []
    for arc in door_arcs:
        wall_id, dist_norm = snap_arc_to_wall(arc, proxies, max_snap_norm=0.012)
        if not wall_id:
            continue
        openings.append(Opening(
            id=f"o-{uuid.uuid4().hex[:8]}",
            wall_id=wall_id,
            distance_along_wall_in=dist_norm * inches_per_norm,
            width_in=arc.radius_norm * inches_per_norm,    # arc radius = door width
            height_in=80.0,
            sill_height_in=0.0,
            kind=OpeningKind.DOOR,
            confidence=0.95,
        ))
    return openings
