#!/usr/bin/env python3
"""Ingest a reference PDF -> PlanGraph -> Archicad command tape (or live build).

Usage:
    python scripts/ingest_pdf.py path/to/plan.pdf
    python scripts/ingest_pdf.py path/to/plan.pdf --project "Southbend Western" --level "Ground"
    python scripts/ingest_pdf.py path/to/plan.pdf --force vector
    python scripts/ingest_pdf.py path/to/plan.pdf --apply         # write to Archicad live
    python scripts/ingest_pdf.py path/to/plan.pdf --apply --port 19723

Outputs (in ingest_output/):
    <stem>_plan.json        — PlanGraph
    <stem>_tape.json        — Archicad command tape (always written)
    <stem>_review.html      — visual review report (PDF page + detected walls overlay)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load .env if present (so GEMINI_API_KEY is available).
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from src.ingest import ingest_pdf
from src.ingest.runner import load_config
from src.build import build_plan_in_archicad
from src.connection import ArchicadConnection, DEFAULT_PORT
from src.decide.scheduler import build_schedule
from src.decide.knowledge_enrichment import enrich_schedule
from src.apply.schedule_exporter import export_csv, schedules_to_html
from src.apply.svg_layered_export import export_layered_svg
from src.apply.svg_lossless_export import export_lossless_svg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_pdf")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a reference PDF into Archicad.")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF to ingest.")
    parser.add_argument("--project", type=str, default="", help="Project name.")
    parser.add_argument("--level", type=str, default="Level 1", help="Level/storey label.")
    parser.add_argument("--page", type=int, default=None,
                        help="Force a specific 0-indexed page (else auto-select).")
    parser.add_argument("--force",
                        choices=["vector", "vision", "hybrid", "vector-truth", "vector-hybrid"],
                        default=None,
                        help="Override the parser route. 'vector-hybrid' (RECOMMENDED): "
                             "clean vector walls + Claude rooms snapped to walls. "
                             "'vector-truth' is geometry-only via planar-graph. "
                             "'hybrid' is the legacy vector+AI mix. "
                             "'vision' is AI-only (raster fallback).")
    parser.add_argument("--apply", action="store_true",
                        help="Push the built elements into a live Archicad project.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Archicad JSON API port (default 19723).")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Output directory (default: ./ingest_output)")
    parser.add_argument("--scale", type=str, default=None,
                        help='Override scale: "1/4" or "3/16" (= 1 foot), or raw decimal.')
    parser.add_argument("--min-line-width", type=float, default=None,
                        help="Drop lines thinner than this (PDF points). Useful for "
                             "Matterport / dense plans (try 0.36).")
    parser.add_argument("--reference-pdf", type=Path, default=None,
                        help="Reference PDF (e.g. Matterport scan) — used as additional "
                             "context for the vision parser to verify scale/proportions.")
    parser.add_argument("--reference-page", type=int, default=0,
                        help="Page index of the reference PDF (default 0).")
    parser.add_argument("--anchor-bbox", type=str, default=None,
                        help="Manual drawing-area override as 'x0,y0,x1,y1' in [0,1] "
                             "image-space (top-left origin). Bypasses Gemini's guess.")
    parser.add_argument("--no-refine-anchor", action="store_true",
                        help="Skip the focused second-pass anchor call (saves one Gemini "
                             "request; lower-quality alignment).")
    parser.add_argument("--vision-provider", type=str, default=None,
                        choices=["gemini", "anthropic", "claude", "openai"],
                        help="Which vision model provider to use. Defaults to "
                             "VISION_PROVIDER env var, or auto-detected from "
                             "available API keys.")
    parser.add_argument("--no-knowledge", action="store_true",
                        help="Skip knowledge-store enrichment of schedules.")
    parser.add_argument("--permit-mode", action="store_true",
                        help="Include IBC items (use groups, fire ratings, "
                             "egress) when querying the knowledge store.")
    args = parser.parse_args()

    cfg = load_config()
    out_dir = args.out_dir or (REPO_ROOT / cfg.get("output", {}).get("ingest_dir", "ingest_output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.pdf_path.stem

    # ── 1. INGEST ────────────────────────────────────────────────────
    logger.info("Ingesting %s …", args.pdf_path)
    scale_override = _parse_scale(args.scale) if args.scale else None
    anchor_override = None
    if args.anchor_bbox:
        try:
            parts = [float(x) for x in args.anchor_bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("need 4 comma-separated floats")
            anchor_override = parts
        except ValueError as exc:
            logger.error("Bad --anchor-bbox: %s", exc)
            sys.exit(2)
    plan = ingest_pdf(
        args.pdf_path,
        project_name=args.project,
        level_name=args.level,
        page_index=args.page,
        force=args.force,
        scale_override_in_per_pt=scale_override,
        min_line_width_pt_override=args.min_line_width,
        reference_pdf=args.reference_pdf,
        reference_page_index=args.reference_page,
        anchor_bbox_override=anchor_override,
        refine_anchor=not args.no_refine_anchor,
        vision_provider=args.vision_provider,
    )
    logger.info("Plan summary: %s", plan.summary())
    if plan.warnings:
        for w in plan.warnings:
            logger.warning("  ! %s", w)

    plan_path = out_dir / f"{stem}_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2))
    logger.info("Wrote %s", plan_path)

    # ── 2. BUILD ─────────────────────────────────────────────────────
    build_cfg = cfg.get("build", {})
    tape_path = out_dir / f"{stem}_tape.json"

    conn = None
    if args.apply:
        try:
            conn = ArchicadConnection(port=args.port).connect()
        except Exception as exc:
            logger.error("Live Archicad connection failed (%s). Writing tape only.", exc)
            conn = None

    result = build_plan_in_archicad(
        plan,
        conn=conn,
        tape_out=tape_path,
        layer_existing=build_cfg.get("wall_layer_existing", "A-Wall-Existing"),
        layer_demo=build_cfg.get("wall_layer_demo", "A-Wall-Demo"),
        layer_new=build_cfg.get("wall_layer_new", "A-Wall-New"),
        default_wall_height_in=build_cfg.get("default_wall_height_in", 108.0),
    )

    logger.info(
        "Build result: walls=%d doors=%d windows=%d zones=%d skipped=%d",
        result.walls_created, result.doors_created,
        result.windows_created, result.zones_created, len(result.skipped),
    )
    if result.skipped:
        logger.info("First 5 skipped: %s", result.skipped[:5])

    # ── 3. CD SCHEDULES ──────────────────────────────────────────────
    sched = build_schedule(plan)

    if not args.no_knowledge:
        try:
            from src.knowledge import KnowledgeStore
            store = KnowledgeStore()
            if store.count() == 0:
                logger.warning(
                    "Knowledge DB is empty. Run "
                    "`python scripts/build_knowledge_db.py` to populate it."
                )
            else:
                logger.info(
                    "Enriching schedules with knowledge store (%d items, "
                    "permit_mode=%s) …",
                    store.count(), args.permit_mode,
                )
                enrich_schedule(sched, store, permit_mode=args.permit_mode)
        except Exception as exc:
            logger.warning("Knowledge enrichment skipped: %s", exc)

    schedules_dir = out_dir / f"{stem}_schedules"
    csv_paths = export_csv(sched, schedules_dir)
    schedule_json = out_dir / f"{stem}_schedule.json"
    schedule_json.write_text(sched.model_dump_json(indent=2))
    logger.info(
        "Schedules: %d doors, %d windows, %d rooms, %d wall-types  →  %s",
        len(sched.doors), len(sched.windows), len(sched.rooms),
        len(sched.wall_types), schedules_dir,
    )

    # ── 4. LOSSLESS SVG (visually identical to source PDF) ──────────
    # This is the "replicate the PDF" baseline. Every primitive from the
    # source PDF is preserved with exact coordinates, grouped by AIA
    # layer via stroke-weight classification. No AI inference.
    lossless_svg = out_dir / f"{stem}_source.svg"
    try:
        export_lossless_svg(
            args.pdf_path,
            page_index=plan.page.page_index if plan.page else 0,
            out_path=lossless_svg,
            project_title=args.project or "",
            sheet_title="A-101 Floor Plan",
        )
    except Exception as exc:
        logger.warning("Lossless SVG export failed: %s", exc)

    # ── 5. INTERPRETED LAYERED SVG (BIM-tagged from PlanGraph) ──────
    svg_path = out_dir / f"{stem}_layered.svg"
    try:
        export_layered_svg(
            plan, sched, svg_path,
            project_title=args.project or "",
            sheet_title="A-101 Floor Plan",
        )
    except Exception as exc:
        logger.warning("Layered SVG export failed: %s", exc)

    # ── 5. REVIEW REPORT ─────────────────────────────────────────────
    review_path = out_dir / f"{stem}_review.html"
    schedules_html = schedules_to_html(sched).replace(
        'href="schedules/', f'href="{stem}_schedules/'
    )
    # Render the source PDF page as a faded background so the user can
    # eyeball alignment between detected geometry and the original drawing.
    bg_png_relpath = _render_page_for_review(
        args.pdf_path,
        page_index=plan.page.page_index if plan.page else 0,
        out_dir=out_dir,
        stem=stem,
    )
    _write_review_html(
        plan, review_path,
        schedules_html=schedules_html,
        background_image=bg_png_relpath,
    )
    logger.info("Wrote review: %s", review_path)

    if plan.accuracy_report:
        ar = plan.accuracy_report
        logger.info(
            "Accuracy: %s (%d/%d pass, median %.1f%%)",
            ar.overall_status, ar.n_passed, ar.n_checked, ar.median_pct_error,
        )

    print(f"\n✓ Done. Open {review_path} to review.\n")


def _render_page_for_review(pdf_path: Path, *, page_index: int,
                            out_dir: Path, stem: str) -> str:
    """Render the source PDF page to a PNG used as a faded background.

    Returns the filename (relative to out_dir) for use in HTML, or "" on failure.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return ""
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        if page_index < 0 or page_index >= len(pdf):
            return ""
        page = pdf[page_index]
        pil = page.render(scale=150 / 72.0).to_pil()
        bg_path = out_dir / f"{stem}_bg.png"
        pil.save(bg_path, "PNG")
        return bg_path.name
    except Exception as exc:
        logger.warning("Could not render PDF page background: %s", exc)
        return ""


def _parse_scale(s: str) -> float:
    """Parse "1/4", "3/16", or a raw decimal into inches-per-PDF-point.

    "1/4" means 1/4 inch on paper = 1 foot real-world → 48 real-in per PDF-in
    → 48/72 = 0.667 in/pt. Returns the in/pt value.
    """
    s = s.strip()
    if "/" in s and " " not in s:
        # treat as architectural fraction = 1 foot
        num, den = s.split("/")
        ratio = float(num) / float(den)
        real_in_per_pdf_in = 12.0 / ratio
        return real_in_per_pdf_in / 72.0
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"Could not parse --scale {s!r}")


def _write_review_html(plan, out_path: Path, schedules_html: str = "",
                       background_image: str = "") -> None:
    """Render an SVG overlay of the detected walls + opening markers."""
    import math
    walls = plan.walls
    rooms = plan.rooms
    fixtures = getattr(plan, "fixtures", []) or []
    has_geometry = bool(walls or rooms or fixtures)
    if not has_geometry:
        out_path.write_text(
            f"<html><body><h2>No geometry detected for {plan.project_name or 'plan'}.</h2>"
            f"<p>Warnings:</p><pre>{json.dumps(plan.warnings, indent=2)}</pre>"
            f"{schedules_html}</body></html>"
        )
        return

    # Compute bbox over walls AND room polygons AND fixtures so the view fits everything.
    all_pts = []
    for w in walls:
        all_pts.append((w.start.x, w.start.y))
        all_pts.append((w.end.x, w.end.y))
    for r in rooms:
        for p in r.polygon:
            all_pts.append((p.x, p.y))
    for f in fixtures:
        all_pts.append((f.bbox_min.x, f.bbox_min.y))
        all_pts.append((f.bbox_max.x, f.bbox_max.y))
    if not all_pts:
        all_pts = [(0.0, 0.0), (1.0, 1.0)]

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    pad = 24.0
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    width = max_x - min_x
    height = max_y - min_y
    # Internal coordinate system: 1 px per inch. The CSS handles display scale,
    # so the SVG's intrinsic size is the building dimensions in inches.
    px_per_in = 1.0
    svg_w = int(width * px_per_in)
    svg_h = int(height * px_per_in)

    def tx(x): return (x - min_x) * px_per_in

    def ty(y): return svg_h - (y - min_y) * px_per_in  # flip for screen

    status_colors = {
        "Existing": "#444444",
        "Demolition": "#cc4444",
        "New Construction": "#3877e0",
        "Unknown": "#999999",
    }

    parts = [
        f'<svg id="plan-svg" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" '
        f'style="background:#fafafa;width:100%;height:auto;display:block">'
    ]

    # Scale geometry to inches as the SVG unit. Internal stroke widths and
    # font sizes are sized as fractions of the bbox so they scale uniformly.
    diag = math.hypot(width, height) or 100.0
    base_stroke = max(2.0, diag / 300.0)
    base_font = max(6.0, diag / 80.0)

    # Rooms (polygons, drawn first so walls sit on top).
    room_palette = ["#e3f2fd", "#fff3e0", "#f3e5f5", "#e8f5e9", "#fce4ec",
                    "#fffde7", "#ede7f6", "#e1f5fe", "#fbe9e7", "#f1f8e9"]
    for i, r in enumerate(plan.rooms):
        if len(r.polygon) < 3:
            continue
        pts = " ".join(f"{tx(p.x):.1f},{ty(p.y):.1f}" for p in r.polygon)
        fill = room_palette[i % len(room_palette)]
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="#999" '
            f'stroke-width="{base_stroke:.2f}" opacity="0.55"/>'
        )
        cx = sum(p.x for p in r.polygon) / len(r.polygon)
        cy = sum(p.y for p in r.polygon) / len(r.polygon)
        label = (r.name or "ROOM")
        parts.append(
            f'<text x="{tx(cx):.1f}" y="{ty(cy):.1f}" '
            f'font-size="{base_font:.1f}" text-anchor="middle" fill="#222" '
            f'font-weight="600">{html_escape(label)}</text>'
        )
        sub_lines = []
        if r.area_sqft:
            sub_lines.append(f"{r.area_sqft:.0f} sf")
        if getattr(r, "floor_finish", ""):
            sub_lines.append(f"FL: {r.floor_finish}")
        for k, line in enumerate(sub_lines, start=1):
            parts.append(
                f'<text x="{tx(cx):.1f}" y="{ty(cy) + base_font * 1.2 * k:.1f}" '
                f'font-size="{base_font * 0.8:.1f}" text-anchor="middle" fill="#555">'
                f'{html_escape(line)}</text>'
            )

    # Walls on top of rooms.
    for w in walls:
        color = status_colors.get(w.status.value if hasattr(w.status, "value") else str(w.status), "#444")
        stroke = max(base_stroke, w.thickness_in)
        parts.append(
            f'<line x1="{tx(w.start.x):.1f}" y1="{ty(w.start.y):.1f}" '
            f'x2="{tx(w.end.x):.1f}" y2="{ty(w.end.y):.1f}" '
            f'stroke="{color}" stroke-width="{stroke:.1f}" stroke-linecap="butt" '
            f'opacity="0.9"/>'
        )

    # Fixtures (built-ins) — hatched rectangles per kind.
    fixture_styles = {
        "Casework":         ("#8c6e3a", "url(#hatch-casework)"),
        "Plumbing Fixture": ("#3aa9bd", "#c4ecf2"),
        "Equipment":        ("#7a52cc", "#e3d8f7"),
        "Appliance":        ("#a55a2a", "#f2dccb"),
        "Reception Desk":   ("#996633", "#e5d2b8"),
        "Exam Table":       ("#999999", "#dddddd"),
        "Kennel Run":       ("#666666", "#bbbbbb"),
        "Column":           ("#222222", "#666666"),
        "Stair":            ("#444444", "#dcdcdc"),
        "Other Built-in":   ("#777777", "#cccccc"),
    }
    if fixtures:
        # Define a hatch pattern for casework once.
        parts.append(
            '<defs><pattern id="hatch-casework" patternUnits="userSpaceOnUse" '
            'width="8" height="8" patternTransform="rotate(45)">'
            '<rect width="8" height="8" fill="#f0e2c4"/>'
            '<line x1="0" y1="0" x2="0" y2="8" stroke="#8c6e3a" stroke-width="1.2"/>'
            '</pattern></defs>'
        )
    for f in fixtures:
        kind_val = f.kind.value if hasattr(f.kind, "value") else str(f.kind)
        stroke, fill = fixture_styles.get(kind_val, ("#777", "#ccc"))
        x0 = tx(min(f.bbox_min.x, f.bbox_max.x))
        y1 = ty(max(f.bbox_min.y, f.bbox_max.y))
        w = abs(f.bbox_max.x - f.bbox_min.x)
        h = abs(f.bbox_max.y - f.bbox_min.y)
        if w < 1 or h < 1:
            continue
        parts.append(
            f'<rect x="{x0:.1f}" y="{y1:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{base_stroke*0.6:.2f}" '
            f'opacity="0.85"/>'
        )
        if f.name:
            parts.append(
                f'<text x="{x0 + w/2:.1f}" y="{y1 + h/2:.1f}" '
                f'font-size="{base_font * 0.7:.1f}" text-anchor="middle" fill="#222">'
                f'{html_escape(f.name[:24])}</text>'
            )

    # Openings (door/window dots).
    op_radius = max(base_stroke * 1.2, 4.0)
    for o in plan.openings:
        wall = next((w for w in walls if w.id == o.wall_id), None)
        if not wall:
            continue
        dx, dy = wall.end.x - wall.start.x, wall.end.y - wall.start.y
        length = math.hypot(dx, dy) or 1.0
        t = max(0.0, min(1.0, o.distance_along_wall_in / length))
        ox = wall.start.x + t * dx
        oy = wall.start.y + t * dy
        fill = "#e0a022" if o.kind.value == "Door" else "#22c2e0"
        parts.append(
            f'<circle cx="{tx(ox):.1f}" cy="{ty(oy):.1f}" r="{op_radius:.1f}" '
            f'fill="{fill}" stroke="#222" stroke-width="{base_stroke*0.5:.2f}"/>'
        )

    parts.append("</svg>")
    svg = "\n".join(parts)

    # Source PDF image — used in side-by-side and overlay panes.
    src_pdf_name = html_escape(Path(plan.page.source_pdf).name if plan.page else "source")
    pdf_img_html = (
        f'<img src="{html_escape(background_image)}" alt="source plan" />'
        if background_image else
        '<div class="muted small" style="padding:24px">No PDF rendered (install pypdfium2).</div>'
    )

    # Anchored overlay: prefer the geometry's image-norm bbox (calibrated
    # coords from the vision parser). Falls back to drawing_area_norm_bbox
    # if no calibrated geometry-norm bbox is available.
    overlay_svg_positioned = ""
    overlay_disabled_attr = "disabled"
    overlay_note = "(unavailable)"
    pdf_img_html_overlay = pdf_img_html
    anchor_bbox = None
    anchor_kind = ""
    if plan.page and plan.page.geom_norm_bbox:
        anchor_bbox = plan.page.geom_norm_bbox
        anchor_kind = "geometry"
    elif plan.page and plan.page.drawing_area_norm_bbox:
        anchor_bbox = plan.page.drawing_area_norm_bbox
        anchor_kind = "drawing-area"

    if background_image and anchor_bbox:
        x0n, y0n, x1n, y1n = anchor_bbox
        if x1n > x0n and y1n > y0n:
            overlay_inner = "\n".join(parts[1:-1])
            overlay_svg_positioned = (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="none" '
                f'style="left:{x0n * 100:.2f}%;top:{y0n * 100:.2f}%;'
                f'width:{(x1n - x0n) * 100:.2f}%;height:{(y1n - y0n) * 100:.2f}%;'
                f'opacity:0.85">{overlay_inner}</svg>'
            )
            overlay_disabled_attr = ""
            overlay_note = f"({anchor_kind})"

    summary_html = "<ul>" + "".join(
        f"<li><b>{k}:</b> {v}</li>" for k, v in plan.summary().items()
    ) + "</ul>"
    warnings_html = ""
    if plan.warnings:
        warnings_html = "<h3>Warnings</h3><ul>" + "".join(
            f"<li>{html_escape(w)}</li>" for w in plan.warnings
        ) + "</ul>"

    legend = """
    <h3>Legend</h3>
    <ul class="legend">
      <li><span class="swatch wall-existing"></span> Existing wall</li>
      <li><span class="swatch wall-demo"></span> Demolition</li>
      <li><span class="swatch wall-new"></span> New construction</li>
      <li><span class="swatch door"></span> Door</li>
      <li><span class="swatch window"></span> Window</li>
      <li><span class="swatch casework"></span> Casework / built-in</li>
      <li><span class="swatch plumbing"></span> Plumbing fixture</li>
      <li><span class="swatch equip"></span> Equipment</li>
    </ul>
    """

    # Accuracy panel
    ar = plan.accuracy_report
    if ar is not None and ar.n_checked > 0:
        status_color = {"pass": "#2e7d32", "warn": "#ef6c00", "fail": "#c62828"}.get(
            ar.overall_status, "#666"
        )
        rows = "".join(
            f'<tr class="acc-{c.status}"><td>{html_escape(c.callout_text)}</td>'
            f'<td>{c.claimed_in:.1f}"</td><td>{c.measured_in:.1f}"</td>'
            f'<td>{c.delta_pct:+.1f}%</td><td>{c.status.upper()}</td></tr>'
            for c in ar.checks[:30]
        )
        accuracy_html = f"""
        <h3>Accuracy Check
          <span class="acc-badge" style="background:{status_color}">
            {ar.overall_status.upper()}
          </span>
        </h3>
        <p class="muted small">{ar.n_passed} pass / {ar.n_warned} warn / {ar.n_failed} fail
        — median {ar.median_pct_error:.1f}% off, worst {ar.worst_pct_error:.1f}%</p>
        <table class="acc-table">
          <thead><tr><th>Callout</th><th>Claimed</th><th>Measured</th><th>Δ</th><th>Status</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """
    else:
        accuracy_html = (
            '<h3>Accuracy Check</h3>'
            '<p class="muted small">No dimension callouts to verify against. '
            'Pass <code>--reference-pdf</code> with a Matterport scan for ground truth.</p>'
        )

    # Variables that get string-substituted into the template.
    overlay_disabled = overlay_disabled_attr

    out_path.write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Ingest Review — {html_escape(plan.project_name or 'plan')}</title>
<style>
:root {{ --border: #e2e2e2; --muted: #666; --accent: #3877e0; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0; padding: 24px; color: #222; }}
h1 {{ margin: 0 0 4px; }}
h2 {{ margin: 28px 0 8px; padding-bottom: 6px; border-bottom: 2px solid #222; }}
h3 {{ margin: 20px 0 8px; }}
.muted {{ color: var(--muted); margin: 0 0 16px; }}

.layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 24px;
           align-items: start; }}

.viewer-tabs {{ display: flex; gap: 4px; margin-bottom: 10px; }}
.viewer-tabs button {{
    border: 1px solid var(--border); background: #fff; padding: 6px 14px;
    cursor: pointer; border-radius: 6px; font-size: 13px;
}}
.viewer-tabs button.active {{ background: #222; color: #fff; border-color: #222; }}

.viewer {{ display: none; }}
.viewer.active {{ display: block; }}

.split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.split-pane {{
    position: relative; background: #fff; border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
}}
.pane-title {{
    font-size: 12px; font-weight: 600; padding: 8px 12px;
    background: #f6f6f6; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
}}
.pane-viewport {{
    overflow: auto; max-height: 78vh; cursor: grab; padding: 8px;
}}
.pane-viewport:active {{ cursor: grabbing; }}
.pane-inner {{ transform-origin: 0 0; transition: transform 0.08s ease-out;
               display: inline-block; min-width: 100%; }}
.pane-inner img, .pane-inner svg {{ display: block; max-width: none; }}

.stack {{
    position: relative; background: #fff; border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
}}
.stack-viewport {{
    overflow: auto; max-height: 80vh; cursor: grab; padding: 8px;
}}
.stack-inner {{ position: relative; display: inline-block; transform-origin: 0 0; }}
.stack-inner img {{ display: block; max-width: none; }}
.stack-inner svg {{
    position: absolute; pointer-events: none;
}}

.zoom-controls {{
    display: flex; gap: 4px; align-items: center;
    background: rgba(255,255,255,0.95); border: 1px solid var(--border);
    border-radius: 6px; padding: 3px;
}}
.zoom-controls button {{
    border: none; background: none; padding: 4px 8px; cursor: pointer;
    font-size: 13px; border-radius: 4px;
}}
.zoom-controls button:hover {{ background: #f0f0f0; }}

.legend {{ list-style: none; padding: 0; }}
.legend li {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; }}
.swatch {{ display: inline-block; width: 14px; height: 14px; border-radius: 2px; }}
.swatch.wall-existing {{ background: #444; }}
.swatch.wall-demo {{ background: #cc4444; }}
.swatch.wall-new {{ background: #3877e0; }}
.swatch.door {{ background: #e0a022; border-radius: 50%; }}
.swatch.window {{ background: #22c2e0; border-radius: 50%; }}
.swatch.casework {{ background: #f0e2c4; border:1px solid #8c6e3a; }}
.swatch.plumbing {{ background: #c4ecf2; border:1px solid #3aa9bd; }}
.swatch.equip {{ background: #e3d8f7; border:1px solid #7a52cc; }}

.acc-badge {{ display: inline-block; color: white; padding: 2px 8px; border-radius: 4px;
              font-size: 11px; font-weight: 600; margin-left: 6px; vertical-align: middle; }}
.acc-table {{ font-size: 12px; margin-top: 4px; }}
.acc-table tr.acc-pass td:last-child {{ color: #2e7d32; font-weight: 600; }}
.acc-table tr.acc-warn td:last-child {{ color: #ef6c00; font-weight: 600; }}
.acc-table tr.acc-fail td:last-child {{ color: #c62828; font-weight: 600; }}
.small {{ font-size: 12px; }}

.schedule-summary .counts {{
    display: flex; gap: 16px; flex-wrap: wrap; margin: 8px 0 16px;
    color: var(--muted);
}}
.schedule-summary .counts b {{ color: #222; font-size: 18px; }}

table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px;
         font-size: 13px; background: #fff; }}
th, td {{ border: 1px solid var(--border); padding: 6px 10px; text-align: left;
         vertical-align: top; }}
th {{ background: #f6f6f6; font-weight: 600; }}
tbody tr:nth-child(even) {{ background: #fafafa; }}
.csv-link {{ font-size: 12px; font-weight: 400; color: var(--accent);
             text-decoration: none; margin-left: 8px; }}
.csv-link:hover {{ text-decoration: underline; }}

.kb-cell {{ font-size: 12px; line-height: 1.4; max-width: 240px; }}
.kb-code {{ font-family: ui-monospace, monospace; font-weight: 600; color: #555; }}
.kb-layer {{ display: inline-block; font-size: 10px; padding: 1px 5px;
             border-radius: 3px; margin-left: 4px; vertical-align: middle;
             text-transform: uppercase; letter-spacing: 0.04em; }}
.kb-csi {{ background: #e3f2fd; color: #0d47a1; }}
.kb-reference {{ background: #fff3e0; color: #b35900; }}
.kb-ibc {{ background: #fce4ec; color: #ad1457; }}
.kb-office {{ background: #e8f5e9; color: #1b5e20; }}
.kb-score {{ display: inline-block; color: #999; font-size: 10px; margin-left: 6px; }}
.kb-summary {{ margin: 4px 0 16px; }}

ul {{ padding-left: 20px; }}
</style></head>
<body>
<h1>Ingest Review</h1>
<p class="muted">{html_escape(plan.project_name or '(no project name)')} — {html_escape(plan.level_name)} — source: {plan.source.value}</p>

<div class="layout">
  <div>
    <div class="viewer-tabs">
      <button class="tab-btn active" data-tab="split">Side-by-side</button>
      <button class="tab-btn" data-tab="overlay" {overlay_disabled}>Overlay {overlay_note}</button>
      <button class="tab-btn" data-tab="solo">Detected only</button>
      <div style="flex:1"></div>
      <div class="zoom-controls">
        <button onclick="zoomAll(0.8)">−</button>
        <button onclick="zoomAll(1.25)">+</button>
        <button onclick="fitAll()">Fit</button>
        <span class="muted small" style="margin-left:8px">Cmd+wheel zooms · drag pans</span>
      </div>
    </div>

    <!-- Side-by-side view -->
    <div class="viewer active" data-view="split">
      <div class="split">
        <div class="split-pane">
          <div class="pane-title">Source PDF
            <span class="muted small">{src_pdf_name}</span>
          </div>
          <div class="pane-viewport" data-sync="split">
            <div class="pane-inner" data-zoom>
              {pdf_img_html}
            </div>
          </div>
        </div>
        <div class="split-pane">
          <div class="pane-title">Detected geometry
            <span class="muted small">vision parse</span>
          </div>
          <div class="pane-viewport" data-sync="split">
            <div class="pane-inner" data-zoom>{svg}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Overlay view (only when anchor bbox available) -->
    <div class="viewer" data-view="overlay">
      <div class="stack">
        <div class="pane-title">Overlay
          <span class="muted small">detected geometry anchored to drawing area</span>
        </div>
        <div class="stack-viewport" data-sync="overlay">
          <div class="stack-inner" data-zoom>
            {pdf_img_html_overlay}
            {overlay_svg_positioned}
          </div>
        </div>
      </div>
    </div>

    <!-- Solo SVG view -->
    <div class="viewer" data-view="solo">
      <div class="split-pane">
        <div class="pane-title">Detected geometry (full size)</div>
        <div class="pane-viewport" data-sync="solo">
          <div class="pane-inner" data-zoom>{svg}</div>
        </div>
      </div>
    </div>
  </div>

  <div>
    <h3>Summary</h3>{summary_html}
    {legend}
    {accuracy_html}
    {warnings_html}
  </div>
</div>

{schedules_html}

<script>
// ---------- tab switching ----------
document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        if (btn.hasAttribute('disabled')) return;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.viewer').forEach(v => v.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.querySelector(`.viewer[data-view="${{tab}}"]`).classList.add('active');
    }});
}});

// ---------- per-pane zoom state ----------
const zoomState = new WeakMap();
function getZoom(el) {{ return zoomState.get(el) || 1; }}
function setZoom(el, s) {{
    s = Math.max(0.1, Math.min(12, s));
    zoomState.set(el, s);
    el.style.transform = `scale(${{s}})`;
}}

function zoomAll(factor) {{
    document.querySelectorAll('.viewer.active [data-zoom]').forEach(el => {{
        setZoom(el, getZoom(el) * factor);
    }});
}}
function fitAll() {{
    document.querySelectorAll('.viewer.active [data-zoom]').forEach(el => setZoom(el, 1));
    document.querySelectorAll('.viewer.active .pane-viewport, .viewer.active .stack-viewport')
        .forEach(vp => vp.scrollTo(0, 0));
}}

// ---------- mouse-wheel zoom (Cmd/Ctrl + wheel) ----------
document.querySelectorAll('.pane-viewport, .stack-viewport').forEach(vp => {{
    vp.addEventListener('wheel', (e) => {{
        if (!(e.metaKey || e.ctrlKey)) return;
        e.preventDefault();
        const inner = vp.querySelector('[data-zoom]');
        if (inner) setZoom(inner, getZoom(inner) * (e.deltaY < 0 ? 1.1 : 0.9));
    }}, {{ passive: false }});
}});

// ---------- drag to pan ----------
let drag = null;
document.querySelectorAll('.pane-viewport, .stack-viewport').forEach(vp => {{
    vp.addEventListener('mousedown', (e) => {{
        if (e.target.tagName === 'BUTTON') return;
        drag = {{ el: vp, x: e.clientX + vp.scrollLeft, y: e.clientY + vp.scrollTop }};
    }});
}});
window.addEventListener('mouseup', () => {{ drag = null; }});
window.addEventListener('mousemove', (e) => {{
    if (!drag) return;
    drag.el.scrollLeft = drag.x - e.clientX;
    drag.el.scrollTop = drag.y - e.clientY;
    // Sync scroll in split panes.
    if (drag.el.dataset.sync === 'split') {{
        document.querySelectorAll('[data-sync="split"]').forEach(o => {{
            if (o !== drag.el) {{
                o.scrollLeft = drag.el.scrollLeft;
                o.scrollTop = drag.el.scrollTop;
            }}
        }});
    }}
}});
// Sync scroll in split panes on regular wheel scroll too.
document.querySelectorAll('[data-sync="split"]').forEach(vp => {{
    vp.addEventListener('scroll', () => {{
        if (drag) return;
        document.querySelectorAll('[data-sync="split"]').forEach(o => {{
            if (o !== vp) {{ o.scrollLeft = vp.scrollLeft; o.scrollTop = vp.scrollTop; }}
        }});
    }});
}});
</script>
</body></html>""")


def html_escape(s) -> str:
    import html as _html
    return _html.escape(str(s))


if __name__ == "__main__":
    main()
