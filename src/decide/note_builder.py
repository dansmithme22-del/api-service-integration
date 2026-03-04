"""Note builder — assembles final ``SheetNotes`` for each layout.

Combines:
- global project notes (from template config)
- element-driven notes (from rules engine)
- manual / scope notes (from a per-project overrides file, if it exists)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models.data_model import (
    ACLayout,
    Discipline,
    NoteEntry,
    ProjectNotesOutput,
    SheetNotes,
)
from .phase_analyzer import LayoutPhaseReport
from .rules_engine import evaluate_rules, load_rules, load_templates

logger = logging.getLogger(__name__)

_TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "config" / "note_templates.json"
_OVERRIDES_PATH = Path(__file__).resolve().parents[2] / "config" / "manual_overrides.json"


def build_sheet_notes(
    layout: ACLayout,
    report: LayoutPhaseReport,
    rules: list[dict[str, Any]] | None = None,
    templates: dict[str, Any] | None = None,
    manual_overrides: dict[str, Any] | None = None,
) -> SheetNotes:
    """Build the complete ``SheetNotes`` for one layout."""
    if templates is None:
        templates = load_templates()
    if rules is None:
        rules = load_rules()
    if manual_overrides is None:
        manual_overrides = _load_manual_overrides()

    global_notes = templates.get("global_project_notes", {})

    # Element-driven notes from rules engine
    triggered: list[NoteEntry] = evaluate_rules(report, rules, templates)

    # Manual / scope overrides keyed by sheet_id
    sheet_overrides = manual_overrides.get(layout.sheet_id, {})

    return SheetNotes(
        sheet_id=layout.sheet_id,
        sheet_name=layout.layout_name,
        discipline=layout.discipline,
        general_notes=list(global_notes.get("general_notes", [])),
        code_notes=list(global_notes.get("code_notes", [])),
        element_driven_notes=triggered,
        scope_notes=sheet_overrides.get("scope_notes", []),
        manual_notes=sheet_overrides.get("manual_notes", []),
    )


def build_all_notes(
    layouts: list[ACLayout],
    reports: dict[str, LayoutPhaseReport],
    project_name: str = "",
) -> ProjectNotesOutput:
    """Build the complete project notes output for every layout."""
    rules = load_rules()
    templates = load_templates()
    manual_overrides = _load_manual_overrides()
    global_notes = templates.get("global_project_notes", {})

    sheets: list[SheetNotes] = []
    for layout in layouts:
        report = reports.get(layout.guid)
        if report is None:
            logger.warning("No phase report for layout %s", layout.sheet_id)
            continue
        sn = build_sheet_notes(layout, report, rules, templates, manual_overrides)
        sheets.append(sn)

    return ProjectNotesOutput(
        project_name=project_name,
        global_general_notes=list(global_notes.get("general_notes", [])),
        global_code_notes=list(global_notes.get("code_notes", [])),
        sheets=sheets,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manual_overrides() -> dict[str, Any]:
    """Load per-sheet manual overrides if the file exists.

    Expected format:
    {
        "A-101": {
            "scope_notes": ["First floor demo scope …"],
            "manual_notes": ["Coordinate with tenant …"]
        }
    }
    """
    if _OVERRIDES_PATH.exists():
        try:
            return json.loads(_OVERRIDES_PATH.read_text())
        except Exception as exc:
            logger.warning("Could not load manual overrides: %s", exc)
    return {}
