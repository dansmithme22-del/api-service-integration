"""Export a ProjectSchedule as CSV (one per category) and HTML tables.

CSV outputs land under ``<out_dir>/<stem>_schedules/`` with these files:
  doors.csv, windows.csv, rooms.csv, wall_types.csv,
  csi_summary.csv, sheet_matrix.csv

HTML tables are returned as a single ``str`` so the caller can drop them
into the review HTML.
"""

from __future__ import annotations

import csv
import html
import logging
from pathlib import Path

from ..decide.scheduler import ProjectSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_csv(sched: ProjectSchedule, out_dir: Path) -> dict[str, Path]:
    """Write one CSV per schedule type. Returns a dict of category->path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    if sched.doors:
        paths["doors"] = _write_csv(out_dir / "doors.csv", sched.doors)
    if sched.windows:
        paths["windows"] = _write_csv(out_dir / "windows.csv", sched.windows)
    if sched.rooms:
        paths["rooms"] = _write_csv(out_dir / "rooms.csv", sched.rooms)
    if sched.wall_types:
        paths["wall_types"] = _write_csv(out_dir / "wall_types.csv", sched.wall_types)
    if sched.fixtures:
        paths["fixtures"] = _write_csv(out_dir / "fixtures.csv", sched.fixtures)
    if sched.floor_finishes:
        paths["floor_finishes"] = _write_csv(out_dir / "floor_finishes.csv", sched.floor_finishes)
    if sched.csi_summary:
        paths["csi_summary"] = _write_csv(out_dir / "csi_summary.csv", sched.csi_summary)
    if sched.sheet_matrix:
        paths["sheet_matrix"] = _write_csv(out_dir / "sheet_matrix.csv", sched.sheet_matrix)

    logger.info("Wrote %d CSV(s) to %s", len(paths), out_dir)
    return paths


def _write_csv(path: Path, rows: list) -> Path:
    """Dump a list of Pydantic models to CSV using field names as the header.

    ``knowledge_ref`` is unpacked into a few flat columns so the spreadsheet
    has plain text per row rather than a nested JSON blob.
    """
    if not rows:
        return path
    base_fields = [f for f in rows[0].model_dump().keys() if f != "knowledge_ref"]
    has_knowledge = any(getattr(r, "knowledge_ref", None) for r in rows)
    fields = base_fields[:]
    if has_knowledge:
        fields.extend([
            "kb_name", "kb_id", "kb_layer", "kb_csi", "kb_score",
        ])

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            d = r.model_dump()
            kref = d.pop("knowledge_ref", None) or {}
            # Flatten list fields with " | " separator for spreadsheet readability.
            for k, v in d.items():
                if isinstance(v, list):
                    d[k] = " | ".join(str(x) for x in v)
            if has_knowledge:
                d["kb_name"] = kref.get("name", "")
                d["kb_id"] = kref.get("id", "")
                d["kb_layer"] = kref.get("layer", "")
                d["kb_csi"] = kref.get("csi_division", "")
                d["kb_score"] = kref.get("score", "")
            writer.writerow(d)
    return path


# ---------------------------------------------------------------------------
# HTML tables (embedded in the review page)
# ---------------------------------------------------------------------------

def schedules_to_html(sched: ProjectSchedule) -> str:
    """Render every schedule as a stack of <h3> + <table> sections."""
    sections: list[str] = []

    sections.append(_pretty_header_summary(sched))
    sections.append(_knowledge_summary_html(sched))

    if sched.csi_summary:
        sections.append(_table(
            title="CSI Division Summary",
            headers=["Division", "Name", "Item Count", "Marks"],
            rows=[
                [s.code, s.name, s.item_count, ", ".join(s.item_marks[:20])
                 + (" …" if len(s.item_marks) > 20 else "")]
                for s in sched.csi_summary
            ],
            csv_link="schedules/csi_summary.csv",
        ))

    if sched.sheet_matrix:
        sections.append(_table(
            title="Sheet Matrix — what appears on which sheet",
            headers=["Sheet", "Sheet Name", "Category", "Count", "CSI Divisions"],
            rows=[
                [r.sheet_code, r.sheet_name, r.category, r.item_count,
                 ", ".join(r.csi_divisions)]
                for r in sched.sheet_matrix
            ],
            csv_link="schedules/sheet_matrix.csv",
        ))

    if sched.doors:
        sections.append(_table(
            title=f"Door Schedule ({len(sched.doors)} doors)",
            headers=["Mark", "Width", "Height", "Type", "Material", "Frame",
                     "Hardware", "Fire Rating", "CSI", "Sheets", "Notes", "KB Match"],
            rows=[
                [d.mark, _dim(d.width_in), _dim(d.height_in), d.type_,
                 d.material, d.frame, d.hardware_set, d.fire_rating,
                 d.csi_division, ", ".join(d.sheets), d.notes,
                 _kb_cell(d.knowledge_ref)]
                for d in sched.doors
            ],
            csv_link="schedules/doors.csv",
        ))

    if sched.windows:
        sections.append(_table(
            title=f"Window Schedule ({len(sched.windows)} windows)",
            headers=["Mark", "Width", "Height", "Sill", "Type", "Material",
                     "Glazing", "CSI", "Sheets", "Notes", "KB Match"],
            rows=[
                [w.mark, _dim(w.width_in), _dim(w.height_in), _dim(w.sill_height_in),
                 w.type_, w.material, w.glazing, w.csi_division,
                 ", ".join(w.sheets), w.notes, _kb_cell(w.knowledge_ref)]
                for w in sched.windows
            ],
            csv_link="schedules/windows.csv",
        ))

    if sched.rooms:
        total_sqft = sum(r.area_sqft for r in sched.rooms)
        sections.append(_table(
            title=f"Room Schedule ({len(sched.rooms)} rooms, {total_sqft:.0f} sf total)",
            headers=["Mark", "Name", "Area (sf)", "Floor", "Base", "Walls",
                     "Ceiling", "CH", "CSI", "Sheets", "Notes", "KB Match"],
            rows=[
                [r.mark, r.name, f"{r.area_sqft:.0f}", r.floor, r.base, r.walls,
                 r.ceiling, _dim(r.ceiling_height_in) if r.ceiling_height_in else "",
                 r.csi_division, ", ".join(r.sheets), r.notes,
                 _kb_cell(r.knowledge_ref)]
                for r in sched.rooms
            ],
            csv_link="schedules/rooms.csv",
        ))

    if sched.wall_types:
        sections.append(_table(
            title=f"Wall Type Schedule ({len(sched.wall_types)} types)",
            headers=["Mark", "Status", "Thickness", "Height", "Count",
                     "Total LF", "Composition", "Fire Rating", "CSI", "Sheets", "KB Match"],
            rows=[
                [w.mark, w.status, _dim(w.thickness_in), _dim(w.height_in),
                 w.count, f"{w.total_length_ft:.0f}",
                 w.composition, w.fire_rating, w.csi_division, ", ".join(w.sheets),
                 _kb_cell(w.knowledge_ref)]
                for w in sched.wall_types
            ],
            csv_link="schedules/wall_types.csv",
        ))

    if sched.fixtures:
        sections.append(_table(
            title=f"Fixture / Equipment Schedule ({len(sched.fixtures)} items)",
            headers=["Mark", "Kind", "Name", "W", "D", "H", "Remove?", "Room",
                     "CSI", "Sheets", "Notes", "KB Match"],
            rows=[
                [f.mark, f.kind, f.name, _dim(f.width_in), _dim(f.depth_in),
                 _dim(f.height_in),
                 "✓" if f.will_be_removed else "",
                 f.room_id, f.csi_division, ", ".join(f.sheets), f.notes,
                 _kb_cell(f.knowledge_ref)]
                for f in sched.fixtures
            ],
            csv_link="schedules/fixtures.csv",
        ))

    if sched.floor_finishes:
        sections.append(_table(
            title=f"Floor Finish Schedule ({len(sched.floor_finishes)} rooms)",
            headers=["Room", "Name", "Area (sf)", "Finish", "CSI", "Sheets", "Notes", "KB Match"],
            rows=[
                [r.room_mark, r.room_name, f"{r.area_sqft:.0f}", r.finish,
                 r.csi_division, ", ".join(r.sheets), r.notes,
                 _kb_cell(r.knowledge_ref)]
                for r in sched.floor_finishes
            ],
            csv_link="schedules/floor_finishes.csv",
        ))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _pretty_header_summary(sched: ProjectSchedule) -> str:
    return f"""
<section class="schedule-summary">
  <h2>CD Set Schedules</h2>
  <p class="muted">{html.escape(sched.project_name or '(no project)')} — {html.escape(sched.level_name)}</p>
  <div class="counts">
    <span><b>{len(sched.doors)}</b> doors</span>
    <span><b>{len(sched.windows)}</b> windows</span>
    <span><b>{len(sched.rooms)}</b> rooms</span>
    <span><b>{len(sched.wall_types)}</b> wall types</span>
    <span><b>{sum(w.count for w in sched.wall_types)}</b> wall segments</span>
  </div>
</section>"""


def _table(*, title: str, headers: list[str], rows: list[list],
           csv_link: str = "") -> str:
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows
    )
    link = f' <a class="csv-link" href="{csv_link}" download>↓ CSV</a>' if csv_link else ""
    return f"""
<section class="schedule">
  <h3>{html.escape(title)}{link}</h3>
  <table>
    <thead><tr>{head}</tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>"""


def _dim(inches: float) -> str:
    """Format inches as feet-inches if >= 12, else as inches."""
    if not inches:
        return ""
    if inches >= 12:
        feet, rem = divmod(inches, 12)
        return f"{int(feet)}'-{rem:.0f}\""
    return f"{inches:.0f}\""


def _kb_cell(kref: dict) -> str:
    """Compact HTML for the per-row knowledge-store match."""
    if not kref:
        return ""
    name = html.escape(kref.get("name", ""))
    code = kref.get("code", "")
    layer = kref.get("layer", "")
    score = kref.get("score", 0.0)
    badge = f' <span class="kb-layer kb-{layer}">{layer}</span>' if layer else ""
    score_str = f' <span class="kb-score">{score:.2f}</span>' if score else ""
    code_str = f'<span class="kb-code">[{code}]</span> ' if code else ""
    return f'<div class="kb-cell">{code_str}{name}{badge}{score_str}</div>'


def _knowledge_summary_html(sched: "ProjectSchedule") -> str:
    """One-line summary of how many rows got a knowledge match."""
    counts = {
        "Doors": (len(sched.doors),
                  sum(1 for d in sched.doors if d.knowledge_ref)),
        "Windows": (len(sched.windows),
                    sum(1 for w in sched.windows if w.knowledge_ref)),
        "Rooms": (len(sched.rooms),
                  sum(1 for r in sched.rooms if r.knowledge_ref)),
        "Wall types": (len(sched.wall_types),
                       sum(1 for w in sched.wall_types if w.knowledge_ref)),
        "Fixtures": (len(sched.fixtures),
                     sum(1 for f in sched.fixtures if f.knowledge_ref)),
        "Floor finishes": (len(sched.floor_finishes),
                           sum(1 for r in sched.floor_finishes if r.knowledge_ref)),
    }
    total_rows = sum(c[0] for c in counts.values())
    matched = sum(c[1] for c in counts.values())
    if total_rows == 0:
        return ""
    if matched == 0:
        return (
            '<section class="kb-summary"><p class="muted small">'
            'Knowledge enrichment not run (or no matches). Run '
            '<code>python scripts/build_knowledge_db.py</code> to seed it.'
            '</p></section>'
        )
    detail = " · ".join(f"{lbl} {m}/{t}" for lbl, (t, m) in counts.items() if t > 0)
    return f"""
<section class="kb-summary">
  <p class="muted small">
    <b>Knowledge enrichment:</b> {matched}/{total_rows} rows matched · {detail}
  </p>
</section>"""
