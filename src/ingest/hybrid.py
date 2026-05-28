"""Hybrid ingest: vector linework (truth) + vision labels (semantics).

Pipeline:

  1. Render PDF page to PNG (same DPI as VisionConfig).
  2. Extract vector linework from the PDF in image-norm coords.
  3. Pair lines into wall centerlines (image-norm).
  4. Ask the vision parser ALSO — but treat its output as labels/semantics,
     not as geometry-of-record.
  5. Convert vector walls to inches using the vision parser's calibration
     (Claude found a real dimension callout; we use it to anchor scale).
  6. Snap each vision-reported room polygon, opening center, and fixture
     bbox to the nearest vector geometry where possible.

Result: a PlanGraph whose walls are PDF-pixel-accurate, with semantic
labels (room names, opening kinds, fixture types) attached.
"""

from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path
from typing import Optional

from .accuracy_checker import check_plan_accuracy
from .plan_model import (
    IngestSource,
    Opening,
    OpeningKind,
    PageMeta,
    PlanGraph,
    Point,
    Wall,
    WallStatus,
)
from .vector_anchor import (
    NormLine,
    VectorPageNorm,
    clip_to_drawing_area,
    extract_vector_norm,
    pair_walls_norm,
)
from .vision_parser import VisionConfig, _render_pdf_page_to_png

logger = logging.getLogger(__name__)


def hybrid_ingest(
    pdf_path: str | Path,
    page_index: int,
    *,
    project_name: str = "",
    level_name: str = "Level 1",
    vision_config: Optional[VisionConfig] = None,
    min_wall_length_norm: float = 0.02,
    pair_max_sep_norm: float = 0.012,
    min_line_width_pt: float = 0.36,
) -> PlanGraph:
    """Run the hybrid vector+vision ingest on one page.

    Vector linework defines geometry. Vision (Claude/Gemini/GPT) provides
    semantic labels and openings.
    """
    pdf_path = Path(pdf_path)
    cfg = vision_config or VisionConfig()

    # 1) Render PNG at the same DPI the vision parser will use.
    dpi = cfg.image_dpi
    png_bytes = _render_pdf_page_to_png(pdf_path, page_index, dpi=dpi)

    # 2) Vector linework in image-norm coords (full page, before clipping).
    vec_page_full = extract_vector_norm(
        pdf_path,
        page_index,
        dpi=dpi,
        min_line_width_pt=min_line_width_pt,
    )

    # 3) Vision parse FIRST — it gives us the drawing-area bbox we use
    #    to clip vector linework to just the architectural drawing region.
    #    See agent_docs/120_GEOMETRY_FRAMEWORK.md "Drawing composition".
    vision_plan = _vision_parse_for_labels(png_bytes, pdf_path, page_index,
                                            project_name, level_name, cfg)

    # 4) Clip vector lines to the drawing-area bbox — removes title block,
    #    legends, scale bars, and adjacent diagrams from wall detection.
    draw_bbox = (vision_plan.page.drawing_area_norm_bbox
                 if vision_plan.page else None)
    if draw_bbox:
        vec_page = clip_to_drawing_area(vec_page_full, draw_bbox)
    else:
        logger.warning("Vision parser returned no drawing_area_norm_bbox; "
                       "falling back to whole-page vector data.")
        vec_page = vec_page_full

    # 5) Pair lines into walls in image-norm space (now on clipped data).
    pairs = pair_walls_norm(
        vec_page,
        min_wall_len_norm=min_wall_length_norm,
        pair_max_sep_norm=pair_max_sep_norm,
    )

    # 5) Use vision's calibration to convert vector walls to inches.
    inches_per_norm = (vision_plan.page.inches_per_norm if vision_plan.page else 0.0)
    if inches_per_norm <= 0:
        # Fall back: assume 1 in/norm so geometry has SOME scale; warn the user.
        inches_per_norm = 240.0
        vision_plan.warnings.append(
            "Hybrid ingest: vision parser provided no calibration. "
            "Geometry shape is correct but inch dimensions are nominal."
        )
    logger.info("Hybrid: %d vector wall pairs × %.2f in/norm = real-world inches",
                len(pairs), inches_per_norm)

    walls = _walls_from_pairs(pairs, inches_per_norm)

    # 6) Build the merged PlanGraph. Walls come from vector data.
    #    Openings: re-anchor each vision opening to the nearest vector wall.
    openings: list[Opening] = []
    for o in vision_plan.openings:
        op_xy = (o.distance_along_wall_in, 0.0)  # not used; we re-snap below
        # The vision parser already converted opening center to inches and
        # attached to nearest VISION wall. We need to re-attach to the
        # nearest vector wall instead.
        center_in = _opening_center_in(o, vision_plan.walls)
        if center_in is None:
            continue
        wall_id, dist = _attach_to_nearest(center_in[0], center_in[1], walls)
        openings.append(Opening(
            id=o.id,
            wall_id=wall_id,
            distance_along_wall_in=dist,
            width_in=o.width_in,
            sill_height_in=o.sill_height_in,
            kind=o.kind,
            swing_direction=o.swing_direction,
            confidence=0.85,            # higher confidence since wall is vector-truth
        ))

    plan = PlanGraph(
        project_name=project_name,
        level_name=level_name,
        units="imperial",
        source=IngestSource.HYBRID,
        page=PageMeta(
            page_index=page_index,
            source_pdf=str(pdf_path),
            width_in=vec_page.width_pt / 72.0 * 0 + (1.0 * inches_per_norm),
            height_in=vec_page.height_pt / 72.0 * 0 + (1.0 * inches_per_norm),
            detected_scale_text=(vision_plan.page.detected_scale_text
                                 if vision_plan.page else ""),
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
        rooms=vision_plan.rooms,
        fixtures=vision_plan.fixtures,
        annotations=vision_plan.annotations,
        dimension_callouts=vision_plan.dimension_callouts,
        warnings=list(vision_plan.warnings),
    )

    check_plan_accuracy(plan)
    return plan


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _vision_parse_for_labels(png_bytes, pdf_path, page_index,
                              project_name, level_name, cfg):
    """Call the vision parser for labels only — same call as raster parse.

    We re-use the existing ``parse_raster_page`` path so calibration, scaling,
    and structured parsing all behave identically. We just discard its walls
    later in favour of the vector-derived ones.
    """
    from .vision_parser import (
        ANCHOR_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
        _dict_to_plan_graph,
        _extract_json,
        _provider_for,
    )

    provider = _provider_for(cfg)
    raw_json = provider.parse_plan(
        png_bytes,
        system_prompt=SYSTEM_PROMPT,
        max_output_tokens=32768,
        temperature=0.1,
    )
    d = _extract_json(raw_json)
    return _dict_to_plan_graph(
        d,
        pdf_path=str(pdf_path),
        page_index=page_index,
        project_name=project_name,
        level_name_default=level_name,
    )


def _walls_from_pairs(pairs: list[tuple[NormLine, NormLine]],
                      inches_per_norm: float) -> list[Wall]:
    """Convert paired vector lines into ``Wall`` objects in real-world inches.

    image-norm origin is top-left; we flip Y to match the PlanGraph convention
    of bottom-left = (0, 0).
    """
    walls: list[Wall] = []
    for a, b in pairs:
        cx0n = (a.x0 + b.x0) / 2.0
        cy0n = (a.y0 + b.y0) / 2.0
        cx1n = (a.x1 + b.x1) / 2.0
        cy1n = (a.y1 + b.y1) / 2.0
        # Inches with Y-flip.
        sx = cx0n * inches_per_norm
        sy = (1.0 - cy0n) * inches_per_norm
        ex = cx1n * inches_per_norm
        ey = (1.0 - cy1n) * inches_per_norm
        sep_norm = _perp_distance_norm(a, b)
        thickness_in = max(2.5, min(14.0, sep_norm * inches_per_norm))
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


def _walls_norm_bbox(pairs: list[tuple[NormLine, NormLine]]) -> Optional[list[float]]:
    if not pairs:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for a, b in pairs:
        xs.extend([a.x0, a.x1, b.x0, b.x1])
        ys.extend([a.y0, a.y1, b.y0, b.y1])
    return [min(xs), min(ys), max(xs), max(ys)]


def _perp_distance_norm(a: NormLine, b: NormLine) -> float:
    """Avg perpendicular distance (in image-norm) between two near-parallel lines."""
    avx, avy = a.x1 - a.x0, a.y1 - a.y0
    a_len = math.hypot(avx, avy)
    if a_len < 1e-6:
        return 0.0
    nx, ny = -avy / a_len, avx / a_len
    d0 = abs((b.x0 - a.x0) * nx + (b.y0 - a.y0) * ny)
    d1 = abs((b.x1 - a.x0) * nx + (b.y1 - a.y0) * ny)
    return (d0 + d1) / 2.0


def _opening_center_in(opening, walls_vision: list[Wall]) -> Optional[tuple[float, float]]:
    """Return the opening's center point in inches.

    The vision opening was originally placed at a position along one of the
    VISION walls. We recover that position so we can re-anchor to the nearest
    VECTOR wall instead.
    """
    parent = next((w for w in walls_vision if w.id == opening.wall_id), None)
    if parent is None:
        return None
    dx, dy = parent.end.x - parent.start.x, parent.end.y - parent.start.y
    length = math.hypot(dx, dy) or 1.0
    t = max(0.0, min(1.0, opening.distance_along_wall_in / length))
    return (parent.start.x + t * dx, parent.start.y + t * dy)


def _attach_to_nearest(x: float, y: float, walls: list[Wall]) -> tuple[str, float]:
    best_id = ""
    best_dist = math.inf
    best_t = 0.0
    for w in walls:
        ax, ay = w.start.x, w.start.y
        bx, by = w.end.x, w.end.y
        wx, wy = bx - ax, by - ay
        wlen_sq = wx * wx + wy * wy
        if wlen_sq < 1e-6:
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
