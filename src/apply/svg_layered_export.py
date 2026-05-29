"""Layered SVG export — BIM-style 2D output.

Produces a single SVG file in which every detected element is:

  * grouped under a ``<g>`` whose ``id`` is the AIA/NCS layer name,
  * tagged with ``data-csi``, ``data-mark``, ``data-properties`` attributes,
  * given a unique ``id`` so the element can be cross-referenced from
    schedule rows / logs / tables.

The result is a vector drawing that looks like the original plan but is
structurally indexable — open it in Illustrator / Affinity / Inkscape /
Archicad's drawing import and every category is on its own layer with
metadata intact.

Conversion to PDF:
  * If ``cairosvg`` is importable, write a companion ``.pdf`` automatically.
  * Otherwise the SVG itself is a valid vector format that any modern PDF
    workflow ingests.
"""

from __future__ import annotations

import html
import logging
import math
from pathlib import Path
from typing import Optional

from ..decide.scheduler import ProjectSchedule
from ..ingest.plan_model import (
    Fixture,
    Opening,
    OpeningKind,
    PlanGraph,
    Wall,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer style table (matches config/drafting/aia_layers.json)
# ---------------------------------------------------------------------------

LAYER_STYLES: dict[str, dict] = {
    # AIA layer name → SVG stroke / fill / stroke-width style
    "A-WALL-EXST":  {"stroke": "#222",   "fill": "none", "sw_mm": 0.50},
    "A-WALL-DEMO":  {"stroke": "#c62828","fill": "none", "sw_mm": 0.35, "dasharray": "4,3"},
    "A-WALL-NEWW":  {"stroke": "#1565c0","fill": "none", "sw_mm": 0.50},
    "A-WALL-FIRE":  {"stroke": "#c62828","fill": "none", "sw_mm": 0.70},
    "A-DOOR":       {"stroke": "#0277bd","fill": "none", "sw_mm": 0.35},
    "A-GLAZ":       {"stroke": "#0288d1","fill": "none", "sw_mm": 0.35},
    "A-FLOR-WDWK":  {"stroke": "#8c6e3a","fill": "#f0e2c4","fill_opacity": 0.5,"sw_mm": 0.35},
    "A-FLOR-PFIX":  {"stroke": "#3aa9bd","fill": "#c4ecf2","fill_opacity": 0.5,"sw_mm": 0.35},
    "A-EQPM-FIXD":  {"stroke": "#7a52cc","fill": "#e3d8f7","fill_opacity": 0.5,"sw_mm": 0.35},
    "A-FLOR-STRS":  {"stroke": "#666",   "fill": "#dcdcdc","fill_opacity": 0.5,"sw_mm": 0.35},
    "A-COLS":       {"stroke": "#111",   "fill": "#444",   "fill_opacity": 0.8,"sw_mm": 0.50},
    "A-AREA":       {"stroke": "#999",   "fill_opacity": 0.15, "sw_mm": 0.13},
    "A-FLOR-IDEN":  {"stroke": "none",   "fill": "#222",   "font_size_in": 8},
    "A-ANNO-DIMS":  {"stroke": "#666",   "fill": "none", "sw_mm": 0.25},
    "A-ANNO-TEXT":  {"stroke": "none",   "fill": "#555",   "font_size_in": 6},
}

# Each room polygon gets one of these fills to differentiate visually.
ROOM_PALETTE = [
    "#e3f2fd", "#fff3e0", "#f3e5f5", "#e8f5e9", "#fce4ec",
    "#fffde7", "#ede7f6", "#e1f5fe", "#fbe9e7", "#f1f8e9",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_layered_svg(
    plan: PlanGraph,
    schedule: ProjectSchedule,
    out_path: Path,
    *,
    project_title: str = "",
    sheet_title: str = "A-101 Floor Plan",
    page_size_in: tuple[float, float] = (36.0, 24.0),  # ARCH D
    px_per_in: float = 96.0,
) -> Path:
    """Write a layered SVG with one ``<g>`` per AIA layer.

    The SVG is sized for ARCH D paper (36" × 24") at the requested
    on-screen pixel density. The drawing area auto-scales to fit the
    plan's real-world bbox plus a 6% margin.

    Returns the path to the written SVG.
    """
    page_w_px = page_size_in[0] * px_per_in
    page_h_px = page_size_in[1] * px_per_in

    # 1) Determine drawing bbox in inches.
    pts: list[tuple[float, float]] = []
    for w in plan.walls:
        pts.extend([(w.start.x, w.start.y), (w.end.x, w.end.y)])
    for r in plan.rooms:
        pts.extend([(p.x, p.y) for p in r.polygon])
    for f in plan.fixtures:
        pts.extend([(f.bbox_min.x, f.bbox_min.y), (f.bbox_max.x, f.bbox_max.y)])
    if not pts:
        pts = [(0.0, 0.0), (1.0, 1.0)]
    min_x, max_x = min(p[0] for p in pts), max(p[0] for p in pts)
    min_y, max_y = min(p[1] for p in pts), max(p[1] for p in pts)
    pad = max(max_x - min_x, max_y - min_y) * 0.06
    min_x -= pad; min_y -= pad; max_x += pad; max_y += pad
    bbox_w_in = max_x - min_x
    bbox_h_in = max_y - min_y

    # Drawing area = central rectangle leaving 2" for title block on right.
    title_block_in = 6.0
    draw_w_in = page_size_in[0] - title_block_in - 1.0
    draw_h_in = page_size_in[1] - 2.0
    scale_x = draw_w_in / bbox_w_in if bbox_w_in else 1.0
    scale_y = draw_h_in / bbox_h_in if bbox_h_in else 1.0
    scale_in_per_drawing_in = min(scale_x, scale_y)
    # Convert real-world inches → page inches.
    offset_x_in = 0.5
    offset_y_in = 1.0

    def tx(x_in: float) -> float:
        return (offset_x_in + (x_in - min_x) * scale_in_per_drawing_in) * px_per_in

    def ty(y_in: float) -> float:
        # SVG Y is downward; flip
        return (page_size_in[1] - offset_y_in - (y_in - min_y) * scale_in_per_drawing_in) * px_per_in

    def tsize(in_size: float) -> float:
        return in_size * scale_in_per_drawing_in * px_per_in

    # 2) Index schedule rows by element id so we can attach properties.
    room_mark_by_id, door_mark_by_id, window_mark_by_id, fixture_mark_by_id = \
        _index_marks(plan, schedule)

    # 3) Open the SVG with metadata.
    parts: list[str] = []
    parts.append(_svg_header(page_w_px, page_h_px, project_title, sheet_title))

    # CSS for the layered groups — Illustrator/Affinity honour these on import.
    parts.append(_css_for_layers())

    # 4) Each layer is a <g> with id = AIA layer name.
    parts.append(_room_layer(plan.rooms, room_mark_by_id, tx, ty, tsize))
    parts.append(_wall_layer(plan.walls, tx, ty, tsize, scale_in_per_drawing_in))
    parts.append(_opening_layer(
        plan.openings, plan.walls, door_mark_by_id, window_mark_by_id,
        tx, ty, tsize, scale_in_per_drawing_in,
    ))
    parts.append(_fixture_layer(plan.fixtures, fixture_mark_by_id, tx, ty, tsize))
    parts.append(_dimension_layer(plan, tx, ty, tsize))
    parts.append(_title_block(
        plan, project_title, sheet_title,
        page_size_in=page_size_in, px_per_in=px_per_in,
        title_block_in=title_block_in,
    ))

    # 5) Schedule legend — attached as XML comment + invisible group so it's
    # inspectable but doesn't clutter the drawing.
    parts.append(_schedule_metadata_block(schedule))

    parts.append("</svg>")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts))
    logger.info(
        "Wrote layered SVG: %s (walls=%d rooms=%d openings=%d fixtures=%d)",
        out_path, len(plan.walls), len(plan.rooms),
        len(plan.openings), len(plan.fixtures),
    )

    # 6) Best-effort PDF: cairosvg if Cairo is system-installed; otherwise
    # skip silently. The SVG itself is the vector deliverable.
    pdf_path = out_path.with_suffix(".pdf")
    try:
        import io
        import contextlib
        import cairosvg
        # cairosvg.svg2pdf prints library-search errors to stderr before
        # raising; silence stderr around the call so the CLI stays clean.
        with contextlib.redirect_stderr(io.StringIO()):
            cairosvg.svg2pdf(url=str(out_path), write_to=str(pdf_path))
        logger.info("Wrote vector PDF: %s", pdf_path)
    except ImportError:
        logger.info("cairosvg not installed — SVG is the vector deliverable.")
    except Exception:
        logger.info(
            "PDF auto-conversion skipped (Cairo system library not found). "
            "Install with `brew install cairo` to enable, or open the SVG "
            "directly in any vector editor (Affinity, Illustrator, Inkscape)."
        )

    return out_path


# ---------------------------------------------------------------------------
# Mark index helpers
# ---------------------------------------------------------------------------

def _index_marks(plan: PlanGraph, schedule: ProjectSchedule):
    """Map each plan element id to its schedule mark for cross-reference."""
    # rooms are indexed in the same order as plan.rooms in build_schedule
    room = {plan.rooms[i].id: schedule.rooms[i].mark
            for i in range(min(len(plan.rooms), len(schedule.rooms)))}

    door_mark: dict[str, str] = {}
    window_mark: dict[str, str] = {}
    d_idx = w_idx = 0
    for o in plan.openings:
        if o.kind == OpeningKind.DOOR and d_idx < len(schedule.doors):
            door_mark[o.id] = schedule.doors[d_idx].mark
            d_idx += 1
        elif o.kind == OpeningKind.WINDOW and w_idx < len(schedule.windows):
            window_mark[o.id] = schedule.windows[w_idx].mark
            w_idx += 1

    fixture_mark: dict[str, str] = {}
    for i, fx in enumerate(plan.fixtures):
        if i < len(schedule.fixtures):
            fixture_mark[fx.id] = schedule.fixtures[i].mark

    return room, door_mark, window_mark, fixture_mark


# ---------------------------------------------------------------------------
# SVG building blocks
# ---------------------------------------------------------------------------

def _svg_header(w_px: float, h_px: float, project_title: str, sheet_title: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w_px:.0f}" height="{h_px:.0f}" '
        f'viewBox="0 0 {w_px:.0f} {h_px:.0f}" '
        f'data-project="{html.escape(project_title)}" '
        f'data-sheet="{html.escape(sheet_title)}">'
        + "\n<title>" + html.escape(sheet_title) + "</title>"
        + "\n<desc>Layered architectural plan. Each &lt;g&gt; corresponds to "
        + "an AIA/NCS layer. Per-element data-mark, data-csi, data-properties "
        + "attributes carry schedule cross-references.</desc>"
    )


def _css_for_layers() -> str:
    """Inline styles so each AIA layer renders correctly without a stylesheet."""
    rules = []
    for layer, st in LAYER_STYLES.items():
        sw_mm = st.get("sw_mm", 0.35)
        sw_px = sw_mm * 0.0393701 * 96  # mm → in → px
        css = [
            f"stroke: {st.get('stroke', '#222')};",
            f"stroke-width: {sw_px:.2f};",
        ]
        if st.get("fill") and st.get("fill") != "none":
            css.append(f"fill: {st['fill']};")
        else:
            css.append("fill: none;")
        if st.get("fill_opacity") is not None:
            css.append(f"fill-opacity: {st['fill_opacity']};")
        if st.get("dasharray"):
            css.append(f"stroke-dasharray: {st['dasharray']};")
        rules.append(f"  g#{layer} > * {{ " + " ".join(css) + " }")
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def _room_layer(rooms, room_mark_by_id, tx, ty, tsize) -> str:
    if not rooms:
        return '<g id="A-AREA" data-csi="09"/>'
    parts = ['<g id="A-AREA" data-csi="09" data-desc="Area polygons (rooms)">']
    for i, r in enumerate(rooms):
        if len(r.polygon) < 3:
            continue
        fill = ROOM_PALETTE[i % len(ROOM_PALETTE)]
        pts = " ".join(f"{tx(p.x):.1f},{ty(p.y):.1f}" for p in r.polygon)
        mark = room_mark_by_id.get(r.id, f"R{i+1:03d}")
        props = f"area={r.area_sqft}sf;name={r.name or 'ROOM'};floor={r.floor_finish};ceiling={r.ceiling_finish}"
        parts.append(
            f'  <polygon id="{r.id}" data-mark="{mark}" data-csi="09" '
            f'data-aia-layer="A-AREA" data-properties="{html.escape(props)}" '
            f'points="{pts}" fill="{fill}" stroke="#999" stroke-width="0.8" '
            f'fill-opacity="0.45"/>'
        )
        # Room tag text
        cx = sum(p.x for p in r.polygon) / len(r.polygon)
        cy = sum(p.y for p in r.polygon) / len(r.polygon)
        label = r.name or "ROOM"
        parts.append(
            f'  <text x="{tx(cx):.1f}" y="{ty(cy):.1f}" data-mark="{mark}" '
            f'data-aia-layer="A-FLOR-IDEN" font-family="Arial" '
            f'font-size="{tsize(8):.1f}" font-weight="700" text-anchor="middle" '
            f'fill="#222">{html.escape(label)}</text>'
        )
        if r.area_sqft:
            parts.append(
                f'  <text x="{tx(cx):.1f}" y="{ty(cy) + tsize(10):.1f}" '
                f'data-aia-layer="A-FLOR-IDEN" font-family="Arial" '
                f'font-size="{tsize(6):.1f}" text-anchor="middle" fill="#555">'
                f'{r.area_sqft:.0f} SF</text>'
            )
    parts.append("</g>")
    return "\n".join(parts)


def _wall_layer(walls, tx, ty, tsize, scale_in_per_drawing_in: float) -> str:
    groups: dict[str, list[Wall]] = {}
    for w in walls:
        status_str = w.status.value if hasattr(w.status, "value") else str(w.status)
        layer = {
            "Existing": "A-WALL-EXST",
            "Demolition": "A-WALL-DEMO",
            "New Construction": "A-WALL-NEWW",
        }.get(status_str, "A-WALL-EXST")
        groups.setdefault(layer, []).append(w)

    parts: list[str] = []
    for layer, ws in groups.items():
        csi = "02" if layer in ("A-WALL-EXST", "A-WALL-DEMO") else "09"
        parts.append(f'<g id="{layer}" data-csi="{csi}" data-desc="{layer}">')
        for w in ws:
            # Each wall is drawn as a stroked line at the wall thickness.
            x1, y1 = tx(w.start.x), ty(w.start.y)
            x2, y2 = tx(w.end.x), ty(w.end.y)
            thickness_px = w.thickness_in * scale_in_per_drawing_in * 96  # in→px
            length_in = math.hypot(w.end.x - w.start.x, w.end.y - w.start.y)
            props = (
                f"thickness={w.thickness_in:.1f}in;"
                f"length={length_in:.1f}in;"
                f"status={w.status.value if hasattr(w.status,'value') else w.status}"
            )
            parts.append(
                f'  <line id="{w.id}" data-aia-layer="{layer}" data-csi="{csi}" '
                f'data-properties="{html.escape(props)}" '
                f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke-width="{max(0.5, thickness_px):.1f}"/>'
            )
        parts.append("</g>")
    return "\n".join(parts)


def _opening_layer(openings, walls, door_marks, window_marks, tx, ty, tsize,
                   scale_in_per_drawing_in: float) -> str:
    doors = [o for o in openings if o.kind == OpeningKind.DOOR]
    windows = [o for o in openings if o.kind == OpeningKind.WINDOW]
    parts: list[str] = []

    def _opening_position(o: Opening) -> Optional[tuple[float, float, float, float]]:
        """Return (x_center_in, y_center_in, wall_dir_x, wall_dir_y)."""
        wall = next((w for w in walls if w.id == o.wall_id), None)
        if not wall:
            return None
        dx = wall.end.x - wall.start.x
        dy = wall.end.y - wall.start.y
        ln = math.hypot(dx, dy) or 1.0
        t = max(0.0, min(1.0, o.distance_along_wall_in / ln))
        return (wall.start.x + t * dx, wall.start.y + t * dy, dx / ln, dy / ln)

    if doors:
        parts.append('<g id="A-DOOR" data-csi="08" data-desc="Doors">')
        for o in doors:
            pos = _opening_position(o)
            if not pos:
                continue
            cx, cy, ux, uy = pos
            half = (o.width_in / 2.0)
            # Door leaf: a short line in the wall's direction
            x1 = cx - ux * half; y1 = cy - uy * half
            x2 = cx + ux * half; y2 = cy + uy * half
            mark = door_marks.get(o.id, "")
            props = f"width={o.width_in:.0f}in;height={o.height_in:.0f}in"
            # Doorway gap as a wider stroked line (clears the wall)
            parts.append(
                f'  <line id="{o.id}" data-mark="{mark}" data-aia-layer="A-DOOR" '
                f'data-csi="08" data-properties="{html.escape(props)}" '
                f'x1="{tx(x1):.1f}" y1="{ty(y1):.1f}" x2="{tx(x2):.1f}" y2="{ty(y2):.1f}"/>'
            )
            # Door swing as a quarter-circle arc
            # Hinge end: assume left end; swing 90° to one side
            radius_px = o.width_in * scale_in_per_drawing_in * 96
            hinge_x_in, hinge_y_in = x1, y1
            # Perpendicular vector for arc end
            nx, ny = -uy, ux
            arc_end_x_in = hinge_x_in + nx * o.width_in
            arc_end_y_in = hinge_y_in + ny * o.width_in
            parts.append(
                f'  <path data-mark="{mark}" data-aia-layer="A-DOOR" '
                f'd="M {tx(x2):.1f},{ty(y2):.1f} '
                f'A {radius_px:.1f},{radius_px:.1f} 0 0 1 '
                f'{tx(arc_end_x_in):.1f},{ty(arc_end_y_in):.1f}" '
                f'fill="none" stroke-width="0.8"/>'
            )
            if mark:
                parts.append(
                    f'  <circle data-aia-layer="A-DOOR-IDEN" '
                    f'cx="{tx(cx):.1f}" cy="{ty(cy) - tsize(8):.1f}" r="{tsize(4):.1f}" '
                    f'fill="white" stroke="#0277bd" stroke-width="0.7"/>'
                    f'<text x="{tx(cx):.1f}" y="{ty(cy) - tsize(8) + tsize(2):.1f}" '
                    f'font-family="Arial" font-size="{tsize(4):.1f}" '
                    f'text-anchor="middle" fill="#0277bd">{mark}</text>'
                )
        parts.append("</g>")

    if windows:
        parts.append('<g id="A-GLAZ" data-csi="08" data-desc="Windows">')
        for o in windows:
            pos = _opening_position(o)
            if not pos:
                continue
            cx, cy, ux, uy = pos
            half = (o.width_in / 2.0)
            x1, y1 = cx - ux * half, cy - uy * half
            x2, y2 = cx + ux * half, cy + uy * half
            mark = window_marks.get(o.id, "")
            props = f"width={o.width_in:.0f}in;height={o.height_in:.0f}in;sill={o.sill_height_in:.0f}in"
            parts.append(
                f'  <line id="{o.id}" data-mark="{mark}" data-aia-layer="A-GLAZ" '
                f'data-csi="08" data-properties="{html.escape(props)}" '
                f'x1="{tx(x1):.1f}" y1="{ty(y1):.1f}" x2="{tx(x2):.1f}" y2="{ty(y2):.1f}"/>'
            )
        parts.append("</g>")

    return "\n".join(parts)


def _fixture_layer(fixtures, fixture_marks, tx, ty, tsize) -> str:
    if not fixtures:
        return ""
    parts: list[str] = []
    by_layer: dict[str, list[Fixture]] = {}
    fixture_layer_map = {
        "Casework": "A-FLOR-WDWK",
        "Reception Desk": "A-FLOR-WDWK",
        "Plumbing Fixture": "A-FLOR-PFIX",
        "Equipment": "A-EQPM-FIXD",
        "Appliance": "A-EQPM-FIXD",
        "Exam Table": "A-EQPM-FIXD",
        "Kennel Run": "A-EQPM-FIXD",
        "Column": "A-COLS",
        "Stair": "A-FLOR-STRS",
    }
    for fx in fixtures:
        kind_val = fx.kind.value if hasattr(fx.kind, "value") else str(fx.kind)
        layer = fixture_layer_map.get(kind_val, "A-EQPM-FIXD")
        by_layer.setdefault(layer, []).append(fx)

    csi_for_layer = {
        "A-FLOR-WDWK": "06",
        "A-FLOR-PFIX": "22",
        "A-EQPM-FIXD": "11",
        "A-COLS":      "05",
        "A-FLOR-STRS": "06",
    }

    for layer, fxs in by_layer.items():
        csi = csi_for_layer.get(layer, "11")
        parts.append(f'<g id="{layer}" data-csi="{csi}" data-desc="{layer}">')
        for fx in fxs:
            mark = fixture_marks.get(fx.id, "")
            w_in = abs(fx.bbox_max.x - fx.bbox_min.x)
            d_in = abs(fx.bbox_max.y - fx.bbox_min.y)
            x = tx(min(fx.bbox_min.x, fx.bbox_max.x))
            y = ty(max(fx.bbox_min.y, fx.bbox_max.y))
            w = w_in * tsize(1) / 1.0
            h = d_in * tsize(1) / 1.0
            kind_val = fx.kind.value if hasattr(fx.kind, "value") else str(fx.kind)
            props = (
                f"kind={kind_val};name={fx.name};width={w_in:.0f}in;"
                f"depth={d_in:.0f}in;height={fx.height_in:.0f}in"
            )
            parts.append(
                f'  <rect id="{fx.id}" data-mark="{mark}" '
                f'data-aia-layer="{layer}" data-csi="{csi}" '
                f'data-properties="{html.escape(props)}" '
                f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>'
            )
            if fx.name:
                parts.append(
                    f'  <text x="{x + w/2:.1f}" y="{y + h/2:.1f}" '
                    f'data-aia-layer="A-ANNO-TEXT" font-family="Arial" '
                    f'font-size="{tsize(4):.1f}" text-anchor="middle" fill="#222">'
                    f'{html.escape(fx.name[:18])}</text>'
                )
        parts.append("</g>")
    return "\n".join(parts)


def _dimension_layer(plan, tx, ty, tsize) -> str:
    if not plan.dimension_callouts:
        return ""
    parts = ['<g id="A-ANNO-DIMS" data-csi="01" data-desc="Dimensions">']
    for dc in plan.dimension_callouts:
        x1, y1 = tx(dc.point_a.x), ty(dc.point_a.y)
        x2, y2 = tx(dc.point_b.x), ty(dc.point_b.y)
        lx, ly = tx(dc.label_position.x), ty(dc.label_position.y)
        parts.append(
            f'  <line data-aia-layer="A-ANNO-DIMS" data-value-in="{dc.value_in}" '
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
        parts.append(
            f'  <text x="{lx:.1f}" y="{ly:.1f}" font-family="Arial" '
            f'font-size="{tsize(4):.1f}" text-anchor="middle" fill="#666">'
            f'{html.escape(dc.text)}</text>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _title_block(plan, project_title: str, sheet_title: str,
                 *, page_size_in, px_per_in, title_block_in: float) -> str:
    """Standard right-side title block at the page edge."""
    page_w_px = page_size_in[0] * px_per_in
    page_h_px = page_size_in[1] * px_per_in
    tb_w_px = title_block_in * px_per_in
    tb_x = page_w_px - tb_w_px - 0.5 * px_per_in
    tb_y = 0.5 * px_per_in
    tb_h = page_h_px - 1.0 * px_per_in

    def line_y(i: int) -> float:
        return tb_y + (i + 1) * (0.4 * px_per_in)

    parts = ['<g id="A-ANNO-TTLB" data-csi="01" data-desc="Title block">']
    parts.append(
        f'  <rect x="{tb_x:.1f}" y="{tb_y:.1f}" width="{tb_w_px:.1f}" '
        f'height="{tb_h:.1f}" fill="none" stroke="#111" stroke-width="2"/>'
    )
    # Title block content rows
    rows = [
        ("PROJECT", project_title or plan.project_name or ""),
        ("LEVEL", plan.level_name),
        ("SHEET", sheet_title),
        ("SCALE",
         "1/4\" = 1'-0\"" if (plan.page and plan.page.calibration_dim_in == 0)
         else (plan.page.calibration_dim_text if plan.page else "")),
        ("DRAWN BY", "Pipeline auto-generated"),
        ("DATE", plan.generated_at.strftime("%Y-%m-%d") if hasattr(plan.generated_at, "strftime") else str(plan.generated_at)),
        ("UNITS", plan.units),
    ]
    for i, (label, value) in enumerate(rows):
        y = line_y(i)
        parts.append(
            f'  <text x="{tb_x + 12:.1f}" y="{y:.1f}" font-family="Arial" '
            f'font-size="9" font-weight="600" fill="#111">{label}</text>'
        )
        parts.append(
            f'  <text x="{tb_x + tb_w_px - 12:.1f}" y="{y:.1f}" font-family="Arial" '
            f'font-size="9" text-anchor="end" fill="#333">{html.escape(str(value)[:30])}</text>'
        )
    # Summary counts at the bottom
    summary = plan.summary()
    y0 = tb_y + tb_h - 8 * 14
    for i, (k, v) in enumerate(summary.items()):
        parts.append(
            f'  <text x="{tb_x + 12:.1f}" y="{y0 + i*12:.1f}" font-family="Arial" '
            f'font-size="8" fill="#555">{html.escape(k)}: {v}</text>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _schedule_metadata_block(schedule: ProjectSchedule) -> str:
    """Invisible <metadata> carrying the full ProjectSchedule as JSON.

    Lets downstream tools (Archicad import, Affinity, custom scripts) read
    every schedule row + cross-reference back to elements by data-mark.
    """
    import json as _json
    payload = _json.dumps(schedule.model_dump(mode="json"), default=str)
    return (
        '<metadata id="schedules">'
        f'<schedule xmlns="https://api-service-integration.local/schedule" '
        f'data-payload="{html.escape(payload)}"/>'
        '</metadata>'
    )
