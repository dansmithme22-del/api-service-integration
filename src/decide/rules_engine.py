"""Rules engine — evaluates annotation rules against extracted data.

Rules are loaded from ``config/rules.json``.  Each rule has:
- ``condition`` — what must be true on a layout for the rule to fire
- ``note_section`` — which template to inject

The engine is intentionally simple: iterate rules, evaluate condition against
the ``LayoutPhaseReport``, collect triggered ``NoteEntry`` objects.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models.data_model import NoteEntry, Phase
from .phase_analyzer import LayoutPhaseReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.json"
_TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "config" / "note_templates.json"


def load_rules() -> list[dict[str, Any]]:
    """Load rules from config/rules.json."""
    data = json.loads(_RULES_PATH.read_text())
    return data.get("rules", [])


def load_templates() -> dict[str, Any]:
    """Load note templates from config/note_templates.json."""
    return json.loads(_TEMPLATES_PATH.read_text())


# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------

def _eval_phase_elements_on_sheet(
    condition: dict[str, Any],
    report: LayoutPhaseReport,
) -> bool:
    """True if the layout has ≥ min_count elements in the given phase."""
    phase_str = condition.get("phase", "")
    phase = _str_to_phase(phase_str)
    if phase is None:
        return False
    min_count = condition.get("min_count", 1)
    return report.phase_counts.get(phase, 0) >= min_count


def _eval_phase_element_type_on_sheet(
    condition: dict[str, Any],
    report: LayoutPhaseReport,
) -> bool:
    """True if the layout has ≥ min_count of a specific element type in a phase."""
    phase = _str_to_phase(condition.get("phase", ""))
    if phase is None:
        return False
    element_type = condition.get("element_type", "")
    return report.has_element_type_in_phase(phase, element_type)


def _eval_element_classification_on_sheet(
    condition: dict[str, Any],
    report: LayoutPhaseReport,
) -> bool:
    """True if the layout contains elements with a matching classification."""
    classification = condition.get("classification", "")
    return report.has_classification(classification)


_EVALUATORS: dict[str, Any] = {
    "phase_elements_on_sheet": _eval_phase_elements_on_sheet,
    "phase_element_type_on_sheet": _eval_phase_element_type_on_sheet,
    "element_classification_on_sheet": _eval_element_classification_on_sheet,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_rules(
    report: LayoutPhaseReport,
    rules: list[dict[str, Any]] | None = None,
    templates: dict[str, Any] | None = None,
) -> list[NoteEntry]:
    """Evaluate all rules against a single layout report.

    Returns a list of ``NoteEntry`` objects for rules that fired.
    """
    if rules is None:
        rules = load_rules()
    if templates is None:
        templates = load_templates()

    template_map: dict[str, dict] = templates.get("templates", {})
    triggered: list[NoteEntry] = []

    for rule in rules:
        cond = rule.get("condition", {})
        ctype = cond.get("type", "")
        evaluator = _EVALUATORS.get(ctype)

        if evaluator is None:
            logger.warning("Unknown condition type '%s' in rule '%s'.", ctype, rule.get("id"))
            continue

        if evaluator(cond, report):
            note_sec = rule.get("note_section", {})
            tpl_key = note_sec.get("template_key", "")
            tpl = template_map.get(tpl_key, {})

            triggered.append(NoteEntry(
                trigger_rule_id=rule.get("id", "unknown"),
                section_title=note_sec.get("section_title", tpl.get("section_title", "")),
                body=list(tpl.get("lines", [])),
            ))
            logger.debug(
                "Rule '%s' fired for sheet '%s'.",
                rule.get("id"),
                report.layout.sheet_id,
            )

    return triggered


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHASE_LOOKUP: dict[str, Phase] = {
    "existing": Phase.EXISTING,
    "demolition": Phase.DEMOLITION,
    "new_construction": Phase.NEW_CONSTRUCTION,
    "new construction": Phase.NEW_CONSTRUCTION,
}


def _str_to_phase(s: str) -> Phase | None:
    return _PHASE_LOOKUP.get(s.lower().strip())
