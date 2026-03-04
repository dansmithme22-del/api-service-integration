#!/usr/bin/env python3
"""Full annotation pipeline — Extract → Decide → Apply.

Usage:
    python scripts/run_annotation.py [--port 19723] [--apply property|json|both] [--dry-run]

Modes:
    --apply json       Write SheetNotes.json + per-sheet files (default, safe)
    --apply property   Write note text into Archicad custom properties
    --apply both       Do both
    --dry-run          Run Extract + Decide, print results, but don't Apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.connection import ArchicadConnection, DEFAULT_PORT
from src.extract.elements import get_all_elements, enrich_elements
from src.extract.layouts import get_layouts
from src.extract.renovation import phase_summary
from src.decide.phase_analyzer import analyse_all_layouts
from src.decide.note_builder import build_all_notes
from src.apply.json_exporter import export_json, export_per_sheet_files, export_flat_text
from src.apply.property_writer import write_notes_to_layouts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_annotation")


def main() -> None:
    parser = argparse.ArgumentParser(description="Layout Annotation Automation — Full Pipeline")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--apply", choices=["json", "property", "both"], default="json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-name", type=str, default="")
    args = parser.parse_args()

    # ── 1. CONNECT ────────────────────────────────────────────────────
    logger.info("Connecting to Archicad on port %d …", args.port)
    conn = ArchicadConnection(port=args.port).connect()

    # ── 2. EXTRACT ────────────────────────────────────────────────────
    logger.info("Extracting elements …")
    raw_elements = get_all_elements(conn)
    logger.info("  %d raw elements retrieved.", len(raw_elements))

    elements = enrich_elements(conn, raw_elements)
    logger.info("  %d elements enriched.", len(elements))

    summary = phase_summary(elements)
    logger.info("  Phase summary: %s", summary)

    logger.info("Extracting layouts …")
    layouts = get_layouts(conn)
    logger.info("  %d layouts found.", len(layouts))

    if not layouts:
        logger.warning("No layouts found in the Layout Book — nothing to annotate.")
        sys.exit(0)

    # ── 3. DECIDE ─────────────────────────────────────────────────────
    logger.info("Analysing phases per layout …")
    reports = analyse_all_layouts(layouts, elements)

    logger.info("Building notes …")
    project_name = args.project_name or "Untitled Project"
    notes_output = build_all_notes(layouts, reports, project_name=project_name)
    logger.info("  Built notes for %d sheets.", len(notes_output.sheets))

    if args.dry_run:
        import json
        print("\n" + json.dumps(notes_output.model_dump(mode="json"), indent=2, default=str))
        logger.info("Dry run — no changes written.")
        return

    # ── 4. APPLY ──────────────────────────────────────────────────────
    if args.apply in ("json", "both"):
        export_json(notes_output)
        export_per_sheet_files(notes_output)
        export_flat_text(notes_output)

    if args.apply in ("property", "both"):
        sheet_map = {sn.sheet_id: sn for sn in notes_output.sheets}
        updated = write_notes_to_layouts(conn, layouts, sheet_map)
        logger.info("  Updated %d layout properties.", updated)

    logger.info("Done.")


if __name__ == "__main__":
    main()
