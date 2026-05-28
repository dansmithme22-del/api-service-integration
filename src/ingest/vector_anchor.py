"""Vector-linework extractor that returns lines in *image-normalized* coords.

This bridges the two coordinate systems used elsewhere in the ingest layer:

  * The vision parser works in image-pixel-norm coords [0, 1] from the
    rendered PNG (top-left origin, +Y down).
  * pdfplumber gives us geometry in PDF user units (bottom-left origin,
    1pt = 1/72 inch).

This module flattens curves, normalizes everything into the same image-norm
space the vision parser uses, and returns a ``VectorPageNorm`` ready to be
fused with the vision output.

The output IS the source-of-truth geometry for any vector PDF — Claude is
only used afterward for *labeling* (which group of lines is a room, what
kind of opening, etc.), not for placing geometry.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NormLine:
    """A line segment in image-norm coords (top-left = 0,0; bottom-right = 1,1)."""
    x0: float
    y0: float
    x1: float
    y1: float
    width_norm: float = 0.0          # stroke width in image-norm units

    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def angle_deg(self) -> float:
        a = math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0))
        return a % 180.0


@dataclass
class VectorPageNorm:
    """All vector geometry from a PDF page, in image-norm coords."""
    page_index: int
    width_pt: float                   # PDF user units (1pt = 1/72 inch)
    height_pt: float
    image_width_px: int               # corresponds to the PNG the vision parser saw
    image_height_px: int
    lines: list[NormLine] = field(default_factory=list)


def extract_vector_norm(
    pdf_path: str | Path,
    page_index: int,
    *,
    dpi: int = 200,
    min_line_width_pt: float = 0.0,
) -> VectorPageNorm:
    """Return all vector linework on ``page_index`` in image-norm coords.

    ``dpi`` must match the DPI used when rendering the page to PNG for the
    vision parser, otherwise image-norm coords from vector and vision will
    disagree. Default 200 matches ``VisionConfig.image_dpi``.
    """
    pdf_path = Path(pdf_path)
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber required: pip install pdfplumber") from exc

    raw_lines: list[tuple[float, float, float, float, float]] = []  # x0,y0,x1,y1,width

    with pdfplumber.open(pdf_path) as pdf:
        if page_index < 0 or page_index >= len(pdf.pages):
            raise IndexError(f"page_index {page_index} out of range")
        page = pdf.pages[page_index]
        w_pt, h_pt = float(page.width), float(page.height)

        for ln in page.lines or []:
            width = float(ln.get("linewidth") or ln.get("width") or 0.0)
            if width < min_line_width_pt:
                continue
            raw_lines.append((float(ln["x0"]), float(ln["y0"]),
                              float(ln["x1"]), float(ln["y1"]), width))

        for r in page.rects or []:
            width = float(r.get("linewidth") or r.get("width") or 0.0)
            if width < min_line_width_pt:
                continue
            x0, y0 = float(r["x0"]), float(r["y0"])
            x1, y1 = float(r["x1"]), float(r["y1"])
            raw_lines.extend([
                (x0, y0, x1, y0, width),
                (x1, y0, x1, y1, width),
                (x1, y1, x0, y1, width),
                (x0, y1, x0, y0, width),
            ])

        for c in page.curves or []:
            width = float(c.get("linewidth") or 0.0)
            if width < min_line_width_pt:
                continue
            pts = c.get("pts") or []
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                raw_lines.append((float(p0[0]), float(p0[1]),
                                  float(p1[0]), float(p1[1]), width))

    # Convert PDF user units (bottom-left origin) → image-norm (top-left origin).
    # 1 PDF inch = 72 pt; PNG was rendered at `dpi` pixels per inch.
    # The PNG dimensions in pixels are width_pt * dpi/72.
    # Image-norm x = pdf_x / page_width_pt
    # Image-norm y = (page_height_pt - pdf_y) / page_height_pt  (Y-flip)
    image_w_px = int(w_pt * dpi / 72.0)
    image_h_px = int(h_pt * dpi / 72.0)
    lines_norm: list[NormLine] = []
    for x0, y0, x1, y1, width in raw_lines:
        nx0 = x0 / w_pt
        ny0 = 1.0 - (y0 / h_pt)
        nx1 = x1 / w_pt
        ny1 = 1.0 - (y1 / h_pt)
        # Width is small — convert to norm via either axis (use width axis since
        # walls are usually drawn with a stroke that's a fixed PDF pt thickness).
        width_norm = width / max(w_pt, h_pt)
        lines_norm.append(NormLine(
            x0=nx0, y0=ny0, x1=nx1, y1=ny1, width_norm=width_norm
        ))

    logger.info(
        "Vector page %d: %d lines in image-norm (PNG would be %dx%d at %d DPI).",
        page_index, len(lines_norm), image_w_px, image_h_px, dpi,
    )
    return VectorPageNorm(
        page_index=page_index,
        width_pt=w_pt, height_pt=h_pt,
        image_width_px=image_w_px, image_height_px=image_h_px,
        lines=lines_norm,
    )


def clip_to_drawing_area(
    page: VectorPageNorm,
    drawing_area_norm_bbox: list[float],
    *,
    pad_norm: float = 0.005,
) -> VectorPageNorm:
    """Return a new VectorPageNorm with only lines that fall inside the bbox.

    A line is kept if BOTH endpoints lie within ``drawing_area_norm_bbox``
    (expanded by ``pad_norm`` on every side). Lines that straddle the bbox
    are dropped — title-block leader lines, scale-bar ticks, and adjacent
    drawings tend to do that.

    See ``agent_docs/120_GEOMETRY_FRAMEWORK.md`` for why this matters: a
    PDF sheet is a composition, not one drawing, and only the line work
    inside the floor-plan drawing region is architectural geometry.
    """
    if not drawing_area_norm_bbox or len(drawing_area_norm_bbox) != 4:
        return page
    x0, y0, x1, y1 = drawing_area_norm_bbox
    x0 -= pad_norm; y0 -= pad_norm
    x1 += pad_norm; y1 += pad_norm

    def inside(x: float, y: float) -> bool:
        return x0 <= x <= x1 and y0 <= y <= y1

    kept = [l for l in page.lines
            if inside(l.x0, l.y0) and inside(l.x1, l.y1)]
    logger.info(
        "Clipped vector lines to drawing area %s: %d → %d",
        drawing_area_norm_bbox, len(page.lines), len(kept),
    )
    return VectorPageNorm(
        page_index=page.page_index,
        width_pt=page.width_pt,
        height_pt=page.height_pt,
        image_width_px=page.image_width_px,
        image_height_px=page.image_height_px,
        lines=kept,
    )


def pair_walls_norm(
    page: VectorPageNorm,
    *,
    min_wall_len_norm: float = 0.02,    # ~ 2% of image width
    pair_max_sep_norm: float = 0.012,   # ~ 1.2% of image width
    angle_tol_deg: float = 4.0,
    min_line_width_norm: float = 0.0,
) -> list[tuple[NormLine, NormLine]]:
    """Find pairs of near-parallel, close-spaced wall edges in image-norm space.

    Same algorithm as the older ``geometry_normalizer.pair_walls`` but driven
    by image-norm thresholds so it composes with the vision parser cleanly.
    """
    long_lines = [
        l for l in page.lines
        if l.length() >= min_wall_len_norm and l.width_norm >= min_line_width_norm
    ]
    pairs: list[tuple[NormLine, NormLine]] = []
    used: set[int] = set()
    for i, a in enumerate(long_lines):
        if i in used:
            continue
        a_angle = a.angle_deg()
        a_len = a.length()
        ax_mid = (a.x0 + a.x1) / 2.0
        ay_mid = (a.y0 + a.y1) / 2.0
        avx, avy = a.x1 - a.x0, a.y1 - a.y0
        nx, ny = -avy / a_len, avx / a_len
        best_j, best_sep = -1, math.inf
        for j, b in enumerate(long_lines):
            if j <= i or j in used:
                continue
            d_angle = abs(a_angle - b.angle_deg())
            d_angle = min(d_angle, 180 - d_angle)
            if d_angle > angle_tol_deg:
                continue
            bx_mid = (b.x0 + b.x1) / 2.0
            by_mid = (b.y0 + b.y1) / 2.0
            sep = abs((bx_mid - ax_mid) * nx + (by_mid - ay_mid) * ny)
            if sep > pair_max_sep_norm or sep < 0.0001:
                continue
            if sep < best_sep:
                best_sep = sep
                best_j = j
        if best_j >= 0:
            pairs.append((a, long_lines[best_j]))
            used.add(i)
            used.add(best_j)
    logger.info("Paired %d walls from %d long norm-lines.", len(pairs), len(long_lines))
    return pairs
