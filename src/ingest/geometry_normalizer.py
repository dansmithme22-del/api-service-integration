"""Convert RawPageGeometry into a PlanGraph in real-world inches.

Three transformations happen here:

1. **Scale inference** — look at dimension callouts (e.g. ``8'-6"``) and the
   ``1/4" = 1'-0"`` scale annotation, then pick the most consistent
   pts-per-inch value.
2. **Wall pairing** — group near-parallel close-spaced line pairs into single
   wall centerlines with a thickness.
3. **Coordinate normalization** — translate so min(x,y) = (0,0), then convert
   PDF points to inches using the inferred scale.

Output is a ``PlanGraph`` with walls populated. Openings, rooms, and
annotations are populated by ``opening_detector`` and ``room_detector``
modules (added incrementally — for now only walls are guaranteed).
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from .plan_model import (
    IngestSource,
    PageMeta,
    PlanGraph,
    Point,
    Wall,
    WallStatus,
)
from .vector_parser import RawLine, RawPageGeometry, RawText

logger = logging.getLogger(__name__)


# Common architectural drawing scales: ratio of real-world inches per PDF inch.
# At "1/4 inch = 1 foot", 1 PDF inch == 48 real inches.
_SCALE_TABLE: dict[str, float] = {
    "1/16\" = 1'-0\"": 192.0,
    "1/8\" = 1'-0\"": 96.0,
    "3/16\" = 1'-0\"": 64.0,
    "1/4\" = 1'-0\"": 48.0,
    "3/8\" = 1'-0\"": 32.0,
    "1/2\" = 1'-0\"": 24.0,
    "3/4\" = 1'-0\"": 16.0,
    "1\" = 1'-0\"": 12.0,
    "1\" = 10'-0\"": 120.0,
    "1\" = 20'-0\"": 240.0,
    "1\" = 30'-0\"": 360.0,
    "1\" = 40'-0\"": 480.0,
    "1\" = 50'-0\"": 600.0,
}

# Patterns for finding scale text in annotations.
_SCALE_RE = re.compile(
    r"(\d+/\d+|\d+)\s*\"\s*=\s*(\d+)\s*'(?:\s*-\s*(\d+)\s*\")?",
    re.IGNORECASE,
)

# Pattern for dimension callouts: 8'-6", 12'-0", 8 ft 6 in, etc.
# Captures feet and inches separately so we can compute total real-world inches.
_DIM_FEET_INCHES_RE = re.compile(
    r"(\d+)\s*'\s*-?\s*(\d+)?\s*\"?",
)


@dataclass
class ScaleResult:
    inches_per_pt: float           # multiply (PDF point) by this to get real inches
    source: str                    # "scale_text:1/4\" = 1'-0\"" or "default"
    confidence: float


def infer_scale(geom: RawPageGeometry, override_in_per_pt: Optional[float] = None) -> ScaleResult:
    """Determine the PDF-inch -> real-inch scale.

    Strategy (in order):
      0. If ``override_in_per_pt`` is provided, use it directly.
      1. Scan text spans for an explicit scale string (e.g. ``1/4" = 1'-0"``).
      2. Calibrate from the largest dimension callout: find dim text like
         ``111'-1"``, locate the longest line nearby on the same horizontal,
         and compute scale from the ratio.
      3. Reasoning from page extent: if a building dimension is >= 50 ft,
         assume that's the long axis of the page and back-calculate.
      4. Default to 1/4" = 1'-0" with low confidence.
    """
    if override_in_per_pt is not None:
        return ScaleResult(
            inches_per_pt=override_in_per_pt,
            source=f"manual_override:{override_in_per_pt:.4f}",
            confidence=1.0,
        )

    # 1) Explicit scale text
    for t in geom.texts:
        m = _SCALE_RE.search(t.text)
        if not m:
            continue
        key = _normalize_scale(m.group(0))
        if key in _SCALE_TABLE:
            real_in_per_pdf_in = _SCALE_TABLE[key]
            return ScaleResult(
                inches_per_pt=real_in_per_pdf_in / 72.0,
                source=f"scale_text:{key}",
                confidence=0.95,
            )

    # 2/3) Calibrate from the largest dimension callout vs page extents.
    largest_dim_in = _largest_dimension_in_inches(geom)
    if largest_dim_in is not None and largest_dim_in >= 50 * 12:  # >= 50 ft
        # Heuristic: a 50+ foot dimension is likely the building's overall length
        # and corresponds to roughly the larger page axis (minus title-block margin).
        page_long_pt = max(geom.width_pt, geom.height_pt)
        # Assume the dimension spans ~85% of the long axis (leaves room for margins).
        usable_pt = page_long_pt * 0.85
        in_per_pt = largest_dim_in / usable_pt
        return ScaleResult(
            inches_per_pt=in_per_pt,
            source=f"dim_calibration:{largest_dim_in/12:.1f}ft_across_{usable_pt:.0f}pt",
            confidence=0.6,
        )

    # 4) Default
    return ScaleResult(
        inches_per_pt=48.0 / 72.0,
        source="default:1/4\" = 1'-0\"",
        confidence=0.3,
    )


def _largest_dimension_in_inches(geom: RawPageGeometry) -> Optional[float]:
    """Scan text spans for feet-and-inches callouts, return the largest in inches."""
    best = 0.0
    for t in geom.texts:
        for m in _DIM_FEET_INCHES_RE.finditer(t.text):
            try:
                feet = int(m.group(1))
            except (TypeError, ValueError):
                continue
            inches = 0
            if m.group(2):
                try:
                    inches = int(m.group(2))
                except ValueError:
                    inches = 0
            total = feet * 12 + inches
            if total > best:
                best = total
    return best if best > 0 else None


def pair_walls(
    lines: list[RawLine],
    *,
    min_wall_len_pt: float,
    max_thickness_pt: float,
    pair_max_sep_pt: float,
    angle_tol_deg: float = 5.0,
    min_line_width_pt: float = 0.0,
) -> list[tuple[RawLine, RawLine]]:
    """Find pairs of near-parallel, close-spaced lines that look like wall edges.

    Two lines are paired when:
      * both have stroke width >= ``min_line_width_pt`` (drops hatching/dim lines),
      * both longer than ``min_wall_len_pt``,
      * angles differ by less than ``angle_tol_deg``,
      * perpendicular distance between them is less than ``pair_max_sep_pt``,
      * the projections overlap by at least half the shorter line's length.

    Returns the list of pairs; each line participates in at most one pair.
    """
    long_lines = [
        l for l in lines
        if l.length() >= min_wall_len_pt and l.width >= min_line_width_pt
    ]
    pairs: list[tuple[RawLine, RawLine]] = []
    used: set[int] = set()

    for i, a in enumerate(long_lines):
        if i in used:
            continue
        a_angle = a.angle_deg()
        a_vec = (a.x1 - a.x0, a.y1 - a.y0)
        a_len = a.length()
        ax_mid = (a.x0 + a.x1) / 2.0
        ay_mid = (a.y0 + a.y1) / 2.0
        # Normal to a (unit) — used for perpendicular distance.
        nx, ny = (-a_vec[1] / a_len, a_vec[0] / a_len)

        best_j = -1
        best_sep = math.inf
        for j, b in enumerate(long_lines):
            if j <= i or j in used:
                continue
            d_angle = abs(a_angle - b.angle_deg())
            d_angle = min(d_angle, 180 - d_angle)
            if d_angle > angle_tol_deg:
                continue
            # Perp distance from line a to midpoint of b.
            bx_mid = (b.x0 + b.x1) / 2.0
            by_mid = (b.y0 + b.y1) / 2.0
            sep = abs((bx_mid - ax_mid) * nx + (by_mid - ay_mid) * ny)
            if sep > pair_max_sep_pt or sep < 0.1:
                continue
            # Projection overlap.
            if not _segments_overlap(a, b):
                continue
            if sep < best_sep:
                best_sep = sep
                best_j = j

        if best_j >= 0:
            pairs.append((a, long_lines[best_j]))
            used.add(i)
            used.add(best_j)

    logger.info("Paired %d walls from %d long lines.", len(pairs), len(long_lines))
    return pairs


def build_plan_graph(
    geom: RawPageGeometry,
    *,
    pdf_path: str,
    project_name: str = "",
    level_name: str = "Level 1",
    min_wall_length_in: float = 6.0,
    max_wall_thickness_in: float = 12.0,
    pair_max_separation_in: float = 14.0,
    min_line_width_pt: float = 0.0,
    scale_override_in_per_pt: Optional[float] = None,
) -> PlanGraph:
    """Normalize a raw page into a PlanGraph (in inches, origin at bbox min)."""
    scale = infer_scale(geom, override_in_per_pt=scale_override_in_per_pt)
    in_per_pt = scale.inches_per_pt
    pt_per_in = 1.0 / in_per_pt

    pairs = pair_walls(
        geom.lines,
        min_wall_len_pt=min_wall_length_in * pt_per_in,
        max_thickness_pt=max_wall_thickness_in * pt_per_in,
        pair_max_sep_pt=pair_max_separation_in * pt_per_in,
        min_line_width_pt=min_line_width_pt,
    )

    walls: list[Wall] = []
    for a, b in pairs:
        cx0 = ((a.x0 + b.x0) / 2.0) * in_per_pt
        cy0 = ((a.y0 + b.y0) / 2.0) * in_per_pt
        cx1 = ((a.x1 + b.x1) / 2.0) * in_per_pt
        cy1 = ((a.y1 + b.y1) / 2.0) * in_per_pt
        thickness_in = _perpendicular_distance(a, b) * in_per_pt
        # Enforce max thickness — anything thicker is almost certainly not a wall
        # (likely a fixture outline that paired across its bounding box).
        if thickness_in > max_wall_thickness_in:
            continue
        # Enforce min length on the centerline (post-scale) too.
        center_len_in = math.hypot(cx1 - cx0, cy1 - cy0)
        if center_len_in < min_wall_length_in:
            continue
        walls.append(Wall(
            id=f"w-{uuid.uuid4().hex[:8]}",
            start=Point(x=cx0, y=cy0),
            end=Point(x=cx1, y=cy1),
            thickness_in=max(thickness_in, 2.5),
            status=WallStatus.EXISTING,
            confidence=scale.confidence,
            source_note=f"vector pair, in/pt={in_per_pt:.4f}",
        ))

    # Translate so min(x,y) = 0.
    if walls:
        xs = [p.x for w in walls for p in (w.start, w.end)]
        ys = [p.y for w in walls for p in (w.start, w.end)]
        min_x, min_y = min(xs), min(ys)
        for w in walls:
            w.start = Point(x=w.start.x - min_x, y=w.start.y - min_y)
            w.end = Point(x=w.end.x - min_x, y=w.end.y - min_y)

    plan = PlanGraph(
        project_name=project_name,
        level_name=level_name,
        units="imperial",
        source=IngestSource.VECTOR,
        page=PageMeta(
            page_index=geom.page_index,
            source_pdf=pdf_path,
            width_in=geom.width_pt * in_per_pt,
            height_in=geom.height_pt * in_per_pt,
            scale_factor_in_per_pdf_unit=in_per_pt,
            detected_scale_text=scale.source,
            is_vector=True,
            confidence=scale.confidence,
        ),
        walls=walls,
    )

    if scale.confidence < 0.5:
        plan.warnings.append(
            f"Scale was guessed ({scale.source}); verify against a known dimension."
        )
    if not walls:
        plan.warnings.append(
            "No walls detected. Either the PDF is raster, or the line-pair "
            "thresholds in config/ingest.json are too tight."
        )

    return plan


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _normalize_scale(s: str) -> str:
    """Normalize a regex match like ``1/4" = 1'-0"`` to the dict key form."""
    s = s.replace(" ", "")
    s = s.replace("”", "\"").replace("’", "'").replace("‘", "'").replace("“", "\"")
    # Reformat to canonical: 1/4" = 1'-0"
    m = _SCALE_RE.search(s)
    if not m:
        return s
    num = m.group(1)
    feet = m.group(2)
    extra_in = m.group(3) or "0"
    return f"{num}\" = {feet}'-{extra_in}\""


def _segments_overlap(a: RawLine, b: RawLine) -> bool:
    """Project b onto a's direction; return True if projection overlaps a."""
    ax, ay = a.x0, a.y0
    avx, avy = a.x1 - a.x0, a.y1 - a.y0
    a_len_sq = avx * avx + avy * avy
    if a_len_sq < 1e-6:
        return False

    def proj(px: float, py: float) -> float:
        return ((px - ax) * avx + (py - ay) * avy) / a_len_sq

    t0 = proj(b.x0, b.y0)
    t1 = proj(b.x1, b.y1)
    lo, hi = (t0, t1) if t0 < t1 else (t1, t0)
    return hi > 0.0 and lo < 1.0


def _perpendicular_distance(a: RawLine, b: RawLine) -> float:
    """Average perpendicular distance from b's endpoints to the infinite line a."""
    avx, avy = a.x1 - a.x0, a.y1 - a.y0
    a_len = math.hypot(avx, avy)
    if a_len < 1e-6:
        return 0.0
    nx, ny = -avy / a_len, avx / a_len
    d0 = abs((b.x0 - a.x0) * nx + (b.y0 - a.y0) * ny)
    d1 = abs((b.x1 - a.x0) * nx + (b.y1 - a.y0) * ny)
    return (d0 + d1) / 2.0
