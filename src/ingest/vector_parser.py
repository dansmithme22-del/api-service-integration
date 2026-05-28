"""Vector-PDF parser: pdfplumber lines/curves/text -> raw wall candidates.

This module does **only** the extraction step. Geometry normalization (scale,
snapping, pairing into wall centerlines) lives in geometry_normalizer.py.

Output of this module is a ``RawPageGeometry`` — lists of straight-line
segments, arc candidates, and text labels, all in PDF user units (points).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RawLine:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float = 0.0           # stroke width in PDF user units

    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def angle_deg(self) -> float:
        """Angle in degrees, normalised to [0, 180)."""
        a = math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0))
        a = a % 180.0
        return a


@dataclass
class RawArc:
    cx: float
    cy: float
    radius: float
    start_angle_deg: float
    end_angle_deg: float


@dataclass
class RawText:
    text: str
    x: float
    y: float
    size: float = 0.0


@dataclass
class RawPageGeometry:
    page_index: int
    width_pt: float
    height_pt: float
    lines: list[RawLine] = field(default_factory=list)
    arcs: list[RawArc] = field(default_factory=list)
    texts: list[RawText] = field(default_factory=list)


def parse_vector_page(pdf_path: str | Path, page_index: int) -> RawPageGeometry:
    """Extract all lines, arcs, and text from one PDF page (in PDF user units).

    A "line" here is any pdfplumber line, plus the four sides of every rect.
    Curves are approximated by their bounding boxes for now; refining this
    needs Bezier flattening, which we'll add when we hit a real case for it.
    """
    pdf_path = Path(pdf_path)

    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required. Run: pip install pdfplumber"
        ) from exc

    with pdfplumber.open(pdf_path) as pdf:
        if page_index < 0 or page_index >= len(pdf.pages):
            raise IndexError(f"page_index {page_index} out of range")
        page = pdf.pages[page_index]

        lines: list[RawLine] = []
        for ln in page.lines or []:
            lines.append(RawLine(
                x0=float(ln["x0"]), y0=float(ln["y0"]),
                x1=float(ln["x1"]), y1=float(ln["y1"]),
                width=float(ln.get("linewidth") or ln.get("width") or 0.0),
            ))

        # Treat rect edges as 4 individual lines (very common for walls).
        for r in page.rects or []:
            x0, y0 = float(r["x0"]), float(r["y0"])
            x1, y1 = float(r["x1"]), float(r["y1"])
            lines.extend([
                RawLine(x0, y0, x1, y0),
                RawLine(x1, y0, x1, y1),
                RawLine(x1, y1, x0, y1),
                RawLine(x0, y1, x0, y0),
            ])

        # Curves: store as straight segments between successive sample points.
        # pdfplumber represents curves as dicts with 'pts' = [(x,y), ...].
        arcs: list[RawArc] = []
        for c in page.curves or []:
            pts = c.get("pts") or []
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                lines.append(RawLine(
                    x0=float(p0[0]), y0=float(p0[1]),
                    x1=float(p1[0]), y1=float(p1[1]),
                    width=float(c.get("linewidth") or 0.0),
                ))
            # Cheap arc reconstruction: if there are >=3 points, fit a circle.
            if len(pts) >= 3:
                arc = _try_fit_arc([(float(p[0]), float(p[1])) for p in pts])
                if arc is not None:
                    arcs.append(arc)

        texts: list[RawText] = []
        for ch in page.chars or []:
            # Aggregate per-word later; for now keep raw chars (small PDFs only).
            texts.append(RawText(
                text=str(ch.get("text", "")),
                x=float(ch["x0"]),
                y=float(ch["y0"]),
                size=float(ch.get("size") or 0.0),
            ))
        texts = _coalesce_chars(texts)

        logger.info(
            "Vector page %d: %d lines, %d arcs, %d text spans",
            page_index, len(lines), len(arcs), len(texts),
        )

        return RawPageGeometry(
            page_index=page_index,
            width_pt=float(page.width),
            height_pt=float(page.height),
            lines=lines,
            arcs=arcs,
            texts=texts,
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _try_fit_arc(pts: list[tuple[float, float]]):
    """Cheap circle-fit through first/middle/last point. Returns RawArc or None."""
    if len(pts) < 3:
        return None
    p0, p1, p2 = pts[0], pts[len(pts) // 2], pts[-1]
    # Solve for circumcenter.
    ax, ay = p0
    bx, by = p1
    cx_, cy_ = p2
    d = 2 * (ax * (by - cy_) + bx * (cy_ - ay) + cx_ * (ay - by))
    if abs(d) < 1e-6:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy_)
          + (bx * bx + by * by) * (cy_ - ay)
          + (cx_ * cx_ + cy_ * cy_) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx_ - bx)
          + (bx * bx + by * by) * (ax - cx_)
          + (cx_ * cx_ + cy_ * cy_) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    start = math.degrees(math.atan2(ay - uy, ax - ux))
    end = math.degrees(math.atan2(cy_ - uy, cx_ - ux))
    return RawArc(cx=ux, cy=uy, radius=r, start_angle_deg=start, end_angle_deg=end)


def _coalesce_chars(chars: list[RawText]) -> list[RawText]:
    """Group adjacent same-line, same-size chars into single text spans.

    Crude but adequate: chars whose y centers are within 1pt and x positions
    monotonically increase by <= 2 * size are merged.
    """
    if not chars:
        return []
    # Sort by y desc, then x asc (PDF origin is bottom-left so high y = top).
    chars = sorted(chars, key=lambda c: (-round(c.y), c.x))
    out: list[RawText] = []
    cur = chars[0]
    buf = cur.text
    for c in chars[1:]:
        same_line = abs(c.y - cur.y) <= 1.0
        same_size = abs(c.size - cur.size) <= 0.5
        gap_ok = (c.x - (cur.x + cur.size)) <= max(2.0 * cur.size, 4.0)
        if same_line and same_size and gap_ok:
            # Space if there's a visible gap > half a char width.
            if (c.x - (cur.x + cur.size)) > 0.5 * cur.size:
                buf += " "
            buf += c.text
            cur = RawText(text=buf, x=cur.x, y=cur.y, size=cur.size)
        else:
            out.append(RawText(text=buf, x=cur.x, y=cur.y, size=cur.size))
            cur = c
            buf = c.text
    out.append(RawText(text=buf, x=cur.x, y=cur.y, size=cur.size))
    return out
