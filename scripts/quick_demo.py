#!/usr/bin/env python3
"""Minimal working example — Quick Demo.

This script:
  1. Connects to a running Archicad instance.
  2. Prints available commands (first 20).
  3. Retrieves a small set of elements + their properties.
  4. Identifies renovation status of each element.
  5. Generates a sample SheetNotes JSON output to stdout and to a file.

Usage:
    python scripts/quick_demo.py [--port 19723]

No Archicad running?
    The script has a --mock flag that uses synthetic data so you can see the
    full pipeline without a live connection.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.data_model import (
    ACElement,
    ACLayout,
    Discipline,
    Phase,
    ProjectNotesOutput,
    SheetNotes,
    parse_sheet_id,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("quick_demo")


# -----------------------------------------------------------------------
# Mock data (used when --mock is passed or Archicad is unreachable)
# -----------------------------------------------------------------------

def _mock_elements() -> list[ACElement]:
    """Synthetic elements simulating a small renovation project."""
    return [
        ACElement(guid="aaa-001", element_type="Wall", layer_name="A-Wall-Existing",
                  renovation_status=Phase.EXISTING),
        ACElement(guid="aaa-002", element_type="Wall", layer_name="A-Wall-Demo",
                  renovation_status=Phase.DEMOLITION),
        ACElement(guid="aaa-003", element_type="Wall", layer_name="A-Wall-Demo",
                  renovation_status=Phase.DEMOLITION),
        ACElement(guid="aaa-004", element_type="Wall", layer_name="A-Wall-New",
                  renovation_status=Phase.NEW_CONSTRUCTION),
        ACElement(guid="aaa-005", element_type="Column", layer_name="S-Column-New",
                  renovation_status=Phase.NEW_CONSTRUCTION),
        ACElement(guid="aaa-006", element_type="Object", layer_name="P-Fixture",
                  renovation_status=Phase.NEW_CONSTRUCTION,
                  classification="Plumbing Fixture"),
        ACElement(guid="aaa-007", element_type="Slab", layer_name="A-Slab-Existing",
                  renovation_status=Phase.EXISTING),
        ACElement(guid="aaa-008", element_type="Door", layer_name="A-Door-New",
                  renovation_status=Phase.NEW_CONSTRUCTION),
    ]


def _mock_layouts() -> list[ACLayout]:
    return [
        ACLayout(guid="lay-001", layout_name="A-101 - FIRST FLOOR DEMOLITION PLAN",
                 sheet_id="A-101", discipline=Discipline.ARCHITECTURAL),
        ACLayout(guid="lay-002", layout_name="A-102 - FIRST FLOOR NEW WORK PLAN",
                 sheet_id="A-102", discipline=Discipline.ARCHITECTURAL),
        ACLayout(guid="lay-003", layout_name="P-101 - PLUMBING PLAN",
                 sheet_id="P-101", discipline=Discipline.PLUMBING),
    ]


# -----------------------------------------------------------------------
# Live data (attempts real Archicad connection)
# -----------------------------------------------------------------------

def _live_demo(port: int) -> None:
    from src.connection import ArchicadConnection
    from src.discovery import discover_commands
    from src.extract.elements import get_all_elements, enrich_elements
    from src.extract.layouts import get_layouts
    from src.extract.renovation import phase_summary

    conn = ArchicadConnection(port=port).connect()

    # 1) Print available commands (first 20)
    cmds = discover_commands(conn)
    print(f"\n--- Available Commands (showing first 20 of {len(cmds)}) ---")
    for c in cmds[:20]:
        print(f"  {c['name']}{c['sig']}")

    # 2) Retrieve elements
    raw = get_all_elements(conn)
    print(f"\n--- Retrieved {len(raw)} raw elements ---")
    elements = enrich_elements(conn, raw[:50])  # Limit to 50 for demo speed
    print(f"--- Enriched {len(elements)} elements ---")

    # 3) Renovation summary
    summary = phase_summary(elements)
    print(f"\n--- Renovation Summary ---")
    for phase, count in summary.items():
        print(f"  {phase}: {count}")

    # 4) Layouts
    layouts = get_layouts(conn)
    print(f"\n--- Found {len(layouts)} layouts ---")
    for lay in layouts[:10]:
        print(f"  {lay.sheet_id}  {lay.layout_name}")

    # 5) Build notes (using the decide layer)
    _run_decide_and_export(elements, layouts)


# -----------------------------------------------------------------------
# Shared decide + export logic
# -----------------------------------------------------------------------

def _run_decide_and_export(
    elements: list[ACElement],
    layouts: list[ACLayout],
) -> None:
    from src.decide.phase_analyzer import analyse_all_layouts
    from src.decide.note_builder import build_all_notes
    from src.apply.json_exporter import export_json

    reports = analyse_all_layouts(layouts, elements)

    # Print phase analysis per layout
    print("\n--- Phase Analysis Per Layout ---")
    for guid, report in reports.items():
        print(f"  {report.layout.sheet_id}:")
        for phase, count in report.phase_counts.items():
            print(f"    {phase.value}: {count} elements")
        if report.classification_counts:
            print(f"    Classifications: {dict(report.classification_counts)}")

    # Build notes
    notes_output = build_all_notes(layouts, reports, project_name="Quick Demo Project")

    # Print sample
    print("\n--- Sample SheetNotes Output ---")
    print(json.dumps(notes_output.model_dump(mode="json"), indent=2, default=str)[:3000])

    # Export
    out_path = export_json(notes_output)
    print(f"\n✓ Full output written to {out_path}")

    # Also show flat text for one sheet
    if notes_output.sheets:
        first = notes_output.sheets[0]
        print(f"\n--- Flat Text for {first.sheet_id} ---")
        print(first.render_flat_text())


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Layout Annotation Quick Demo")
    parser.add_argument("--port", type=int, default=19723)
    parser.add_argument("--mock", action="store_true",
                        help="Use synthetic data instead of connecting to Archicad")
    args = parser.parse_args()

    if args.mock:
        print("Running in MOCK mode (no Archicad connection).\n")
        elements = _mock_elements()
        layouts = _mock_layouts()

        print(f"--- {len(elements)} mock elements ---")
        for e in elements:
            status = e.renovation_status.value if e.renovation_status else "N/A"
            print(f"  {e.element_type:10s}  {e.layer_name:25s}  {status}")

        print(f"\n--- {len(layouts)} mock layouts ---")
        for lay in layouts:
            print(f"  {lay.sheet_id}  {lay.layout_name}")

        _run_decide_and_export(elements, layouts)
    else:
        try:
            _live_demo(args.port)
        except Exception as exc:
            print(f"\n✗ Live connection failed: {exc}")
            print("  Falling back to --mock mode.\n")
            elements = _mock_elements()
            layouts = _mock_layouts()
            _run_decide_and_export(elements, layouts)


if __name__ == "__main__":
    main()
