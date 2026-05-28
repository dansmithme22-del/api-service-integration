"""Components → layered SVG.

Output structure — each component gets exactly one ``<g>``:

    <g id="W001" data-kind="Wall" data-mark="W001"
       data-aia="A-WALL-EXST" data-csi="09"
       data-properties='{...full BIM property set...}'>
        <!-- the SVG primitives that draw this wall -->
    </g>

No text glyph noise.  No misclassified curves.  Each component is a
self-contained Revit-Family-like unit: you can select it in Affinity /
Illustrator / Inkscape and immediately see every property that defines
how to build it.

Top-level groups by component kind exist so the layer panel in any
vector editor shows the categories:

    <g id="Walls">     <g id="W001"/> <g id="W002"/> ... </g>
    <g id="Doors">     <g id="D001"/> <g id="D002"/> ... </g>
    <g id="Windows">   <g id="W001"/> ... </g>
    <g id="Floors">    ...
"""

from __future__ import annotations

import html
import json
import logging
import math
from pathlib import Path

from .schemas import Component, ComponentKind

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_components_svg(
    components: list[Component],
    out_path: Path,
    *,
    project_title: str = "",
    sheet_title: str = "A-101 Floor Plan",
    page_size_in: tuple[float, float] = (36.0, 24.0),  # ARCH D
    px_per_in: float = 96.0,
) -> Path:
    """Write a layered SVG, one ``<g>`` per component.

    Returns the SVG path.
    """
    page_w_px = page_size_in[0] * px_per_in
    page_h_px = page_size_in[1] * px_per_in

    # Compute drawing bbox in inches from all component geometry.
    pts = list(_iter_points(components))
    if not pts:
        pts = [(0.0, 0.0), (1.0, 1.0)]
    min_x, max_x = min(p[0] for p in pts), max(p[0] for p in pts)
    min_y, max_y = min(p[1] for p in pts), max(p[1] for p in pts)
    pad = max(max_x - min_x, max_y - min_y) * 0.05
    min_x -= pad; min_y -= pad; max_x += pad; max_y += pad
    bbox_w_in = max_x - min_x
    bbox_h_in = max_y - min_y

    # Fit drawing inside the page minus a 5" title-block column on the right.
    title_w_in = 5.0
    draw_w_in = page_size_in[0] - title_w_in - 1.0
    draw_h_in = page_size_in[1] - 1.0
    scale = min(draw_w_in / bbox_w_in if bbox_w_in else 1.0,
                draw_h_in / bbox_h_in if bbox_h_in else 1.0)
    off_x_in = 0.5
    off_y_in = 0.5

    def tx(x_in: float) -> float:
        return (off_x_in + (x_in - min_x) * scale) * px_per_in

    def ty(y_in: float) -> float:
        return (page_size_in[1] - off_y_in - (y_in - min_y) * scale) * px_per_in

    def tw(in_size: float) -> float:
        return in_size * scale * px_per_in

    # Bucket components by kind so we can produce a clean per-category group.
    by_kind: dict[str, list[Component]] = {}
    for c in components:
        by_kind.setdefault(c.kind.value, []).append(c)

    parts: list[str] = []
    parts.append(_svg_header(page_w_px, page_h_px, project_title, sheet_title,
                             total_components=len(components)))
    parts.append(_white_background(page_w_px, page_h_px))

    # Order: floors (bottom), ceilings, walls, doors, windows, stairs, decks
    order = ["Floor", "Ceiling", "Wall", "Door", "Window", "Stair", "Deck"]
    for kind in order:
        if kind not in by_kind:
            continue
        parts.append(_render_kind_group(kind, by_kind[kind], tx, ty, tw))

    parts.append(_title_block_group(
        page_size_in, px_per_in, title_w_in,
        project_title, sheet_title, components,
    ))

    parts.append("</svg>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts))
    logger.info("Wrote components SVG: %s (%d components)",
                out_path, len(components))
    return out_path


# ---------------------------------------------------------------------------
# Per-kind rendering
# ---------------------------------------------------------------------------

def _render_kind_group(kind: str, comps: list[Component], tx, ty, tw) -> str:
    parts = [f'<g id="{kind}s" data-kind="{kind}" data-count="{len(comps)}">']
    for c in comps:
        parts.append(_render_component(c, tx, ty, tw))
    parts.append("</g>")
    return "\n".join(parts)


def _render_component(c: Component, tx, ty, tw) -> str:
    """Emit one component as a <g> with all properties + its geometry."""
    props = c.describe()
    # data-properties is a compact JSON blob the consumer can parse.
    data_props = html.escape(json.dumps(props, default=str), quote=True)

    parts = [
        f'<g id="{c.mark}" data-kind="{c.kind.value}" data-mark="{c.mark}" '
        f'data-aia="{c.aia_layer}" data-csi="{c.csi_division}" '
        f'data-name="{html.escape(c.name)}" '
        f'data-properties="{data_props}">'
    ]

    for g in c.geometry:
        parts.append(_render_geometry(g, c, tx, ty, tw))

    parts.append("</g>")
    return "\n".join(parts)


def _render_geometry(g: dict, c: Component, tx, ty, tw) -> str:
    kind = g.get("kind")
    if kind == "wall_pair":
        return _render_wall_pair(g, c, tx, ty, tw)
    if kind == "door_swing":
        return _render_door_swing(g, c, tx, ty, tw)
    if kind == "window_segment":
        return _render_window_segment(g, c, tx, ty, tw)
    if kind == "polygon":
        return _render_polygon(g, c, tx, ty, tw)
    return ""


def _render_wall_pair(g: dict, c, tx, ty, tw) -> str:
    """Draw a wall as a stroked centerline at the wall's thickness."""
    x1, y1 = tx(g["start_x"]), ty(g["start_y"])
    x2, y2 = tx(g["end_x"]),   ty(g["end_y"])
    sw = max(0.8, tw(g["thickness_in"]))
    # Existing/demo styling via stroke (vector editors can override).
    stroke = "#111"
    dash = ""
    if c.aia_layer == "A-WALL-DEMO":
        stroke = "#b71c1c"
        dash = ' stroke-dasharray="6,4"'
    elif c.aia_layer == "A-WALL-NEWW":
        stroke = "#0d47a1"
    return (
        f'  <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{sw:.2f}" stroke-linecap="butt"{dash} '
        f'fill="none"/>'
    )


def _render_door_swing(g: dict, c, tx, ty, tw) -> str:
    """Draw door as leaf line + 90° swing arc."""
    cx_in, cy_in = g["center_x"], g["center_y"]
    width_in = g["width_in"]
    dx, dy = g["wall_dx"], g["wall_dy"]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    half = width_in / 2.0
    # Leaf
    hx1, hy1 = cx_in - ux * half, cy_in - uy * half
    hx2, hy2 = cx_in + ux * half, cy_in + uy * half
    # Swing arc from hinge (hx1, hy1) at radius=width, sweeping 90°
    nx, ny = -uy, ux           # perpendicular
    swing_end_x, swing_end_y = hx1 + nx * width_in, hy1 + ny * width_in
    sw_thin = max(0.5, tw(c.leaf_thickness_in) * 0.6)
    r_px = tw(width_in)
    return (
        f'  <line x1="{tx(hx1):.2f}" y1="{ty(hy1):.2f}" '
        f'x2="{tx(hx2):.2f}" y2="{ty(hy2):.2f}" '
        f'stroke="#0d47a1" stroke-width="{sw_thin:.2f}" fill="none"/>\n'
        f'  <path d="M {tx(hx2):.2f},{ty(hy2):.2f} '
        f'A {r_px:.2f},{r_px:.2f} 0 0 1 '
        f'{tx(swing_end_x):.2f},{ty(swing_end_y):.2f}" '
        f'stroke="#0d47a1" stroke-width="{max(0.4, sw_thin*0.7):.2f}" fill="none"/>'
    )


def _render_window_segment(g: dict, c, tx, ty, tw) -> str:
    cx_in, cy_in = g["center_x"], g["center_y"]
    width_in = g["width_in"]
    dx, dy = g["wall_dx"], g["wall_dy"]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    half = width_in / 2.0
    hx1, hy1 = cx_in - ux * half, cy_in - uy * half
    hx2, hy2 = cx_in + ux * half, cy_in + uy * half
    return (
        f'  <line x1="{tx(hx1):.2f}" y1="{ty(hy1):.2f}" '
        f'x2="{tx(hx2):.2f}" y2="{ty(hy2):.2f}" '
        f'stroke="#0277bd" stroke-width="1.4" fill="none"/>'
    )


def _render_polygon(g: dict, c, tx, ty, tw) -> str:
    pts = g.get("points") or []
    if len(pts) < 3:
        return ""
    pts_str = " ".join(f"{tx(p[0]):.2f},{ty(p[1]):.2f}" for p in pts)
    # Floor / ceiling get a faint fill; others just outline.
    fill, stroke, opacity = "none", "#999", "1.0"
    if c.kind == ComponentKind.FLOOR:
        fill, opacity = "#f5f5f0", "0.30"
    elif c.kind == ComponentKind.CEILING:
        fill, opacity = "#e3f2fd", "0.20"
    elif c.kind == ComponentKind.STAIR:
        fill, opacity = "#cccccc", "0.55"
        stroke = "#222"
    return (
        f'  <polygon points="{pts_str}" '
        f'fill="{fill}" fill-opacity="{opacity}" '
        f'stroke="{stroke}" stroke-width="0.6"/>'
    )


# ---------------------------------------------------------------------------
# Header / title block / background
# ---------------------------------------------------------------------------

def _svg_header(w_px: float, h_px: float, project: str, sheet: str,
                *, total_components: int) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w_px:.0f}" height="{h_px:.0f}" '
        f'viewBox="0 0 {w_px:.0f} {h_px:.0f}" '
        f'data-project="{html.escape(project)}" '
        f'data-sheet="{html.escape(sheet)}" '
        f'data-components="{total_components}">\n'
        f'<title>{html.escape(sheet)}</title>\n'
        f'<desc>Component-grouped architectural plan. '
        f'Each &lt;g&gt; is one buildable component with full property '
        f'set in data-properties (JSON). Categories: Walls, Doors, '
        f'Windows, Floors, Ceilings, Stairs, Decks.</desc>'
    )


def _white_background(w_px: float, h_px: float) -> str:
    return (
        f'<rect x="0" y="0" width="{w_px:.0f}" height="{h_px:.0f}" '
        f'fill="white" stroke="none"/>'
    )


def _title_block_group(page_size_in, px_per_in, title_w_in,
                       project: str, sheet: str, components: list[Component]) -> str:
    page_w_px = page_size_in[0] * px_per_in
    page_h_px = page_size_in[1] * px_per_in
    tb_w_px = title_w_in * px_per_in
    tb_x = page_w_px - tb_w_px - 0.4 * px_per_in
    tb_y = 0.4 * px_per_in
    tb_h = page_h_px - 0.8 * px_per_in

    # Count by kind
    counts: dict[str, int] = {}
    for c in components:
        counts[c.kind.value] = counts.get(c.kind.value, 0) + 1

    parts = ['<g id="Title-Block" data-kind="TitleBlock">']
    parts.append(
        f'  <rect x="{tb_x:.1f}" y="{tb_y:.1f}" width="{tb_w_px:.1f}" '
        f'height="{tb_h:.1f}" fill="white" stroke="#000" stroke-width="1.5"/>'
    )
    rows = [
        ("PROJECT", project),
        ("SHEET", sheet),
        ("SCALE", "1/4\" = 1'-0\""),
        ("UNITS", "Imperial inches"),
        ("DRAWING", "BIM-tagged 2D Plan"),
        ("DRAWN", "Pipeline auto-generated"),
    ]
    line_h = 0.34 * px_per_in
    for i, (lbl, val) in enumerate(rows):
        y = tb_y + (i + 1) * line_h
        parts.append(
            f'  <text x="{tb_x + 10:.1f}" y="{y:.1f}" font-family="Arial" '
            f'font-size="10" font-weight="700" fill="#111">{html.escape(lbl)}</text>'
        )
        parts.append(
            f'  <text x="{tb_x + tb_w_px - 10:.1f}" y="{y:.1f}" font-family="Arial" '
            f'font-size="10" text-anchor="end" fill="#333">'
            f'{html.escape(str(val)[:36])}</text>'
        )

    # Component counts at the bottom
    parts.append(
        f'  <text x="{tb_x + 10:.1f}" y="{tb_y + tb_h - line_h * (len(counts) + 1):.1f}" '
        f'font-family="Arial" font-size="11" font-weight="700" fill="#111">'
        f'COMPONENT SUMMARY</text>'
    )
    for i, (kind, count) in enumerate(sorted(counts.items())):
        y = tb_y + tb_h - line_h * len(counts) + i * line_h * 0.8
        parts.append(
            f'  <text x="{tb_x + 10:.1f}" y="{y:.1f}" font-family="Arial" '
            f'font-size="10" fill="#222">{html.escape(kind)}: {count}</text>'
        )
    parts.append("</g>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_points(components: list[Component]):
    for c in components:
        for g in c.geometry:
            k = g.get("kind")
            if k == "wall_pair":
                yield (g["start_x"], g["start_y"])
                yield (g["end_x"], g["end_y"])
            elif k in ("door_swing", "window_segment"):
                yield (g["center_x"], g["center_y"])
            elif k == "polygon":
                for p in g.get("points") or []:
                    yield (p[0], p[1])
