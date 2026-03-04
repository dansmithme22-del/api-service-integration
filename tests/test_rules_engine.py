"""Tests for the rules engine (no Archicad connection needed)."""

from __future__ import annotations

import pytest

from src.models.data_model import ACElement, ACLayout, Discipline, Phase
from src.decide.phase_analyzer import LayoutPhaseReport, analyse_layout
from src.decide.rules_engine import evaluate_rules, load_rules, load_templates


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def demo_layout() -> ACLayout:
    return ACLayout(
        guid="test-lay-001",
        layout_name="A-101 - DEMO PLAN",
        sheet_id="A-101",
        discipline=Discipline.ARCHITECTURAL,
    )


@pytest.fixture
def elements_with_demo() -> list[ACElement]:
    return [
        ACElement(guid="e1", element_type="Wall", renovation_status=Phase.DEMOLITION),
        ACElement(guid="e2", element_type="Wall", renovation_status=Phase.DEMOLITION),
        ACElement(guid="e3", element_type="Wall", renovation_status=Phase.EXISTING),
    ]


@pytest.fixture
def elements_new_only() -> list[ACElement]:
    return [
        ACElement(guid="e4", element_type="Wall", renovation_status=Phase.NEW_CONSTRUCTION),
        ACElement(guid="e5", element_type="Column", renovation_status=Phase.NEW_CONSTRUCTION),
    ]


@pytest.fixture
def elements_with_plumbing() -> list[ACElement]:
    return [
        ACElement(guid="e6", element_type="Object", renovation_status=Phase.NEW_CONSTRUCTION,
                  classification="Plumbing Fixture"),
    ]


# ── Tests ─────────────────────────────────────────────────────────────

class TestRulesEngine:
    def test_demo_elements_trigger_demolition_notes(
        self, demo_layout: ACLayout, elements_with_demo: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_with_demo)
        triggered = evaluate_rules(report)
        ids = [n.trigger_rule_id for n in triggered]
        assert "demo_elements_present" in ids

    def test_no_demo_elements_no_demolition_notes(
        self, demo_layout: ACLayout, elements_new_only: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_new_only)
        triggered = evaluate_rules(report)
        ids = [n.trigger_rule_id for n in triggered]
        assert "demo_elements_present" not in ids

    def test_new_walls_trigger_new_work_notes(
        self, demo_layout: ACLayout, elements_new_only: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_new_only)
        triggered = evaluate_rules(report)
        ids = [n.trigger_rule_id for n in triggered]
        assert "new_walls_present" in ids

    def test_plumbing_triggers_coordination_note(
        self, demo_layout: ACLayout, elements_with_plumbing: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_with_plumbing)
        triggered = evaluate_rules(report)
        ids = [n.trigger_rule_id for n in triggered]
        assert "plumbing_fixtures_present" in ids

    def test_existing_elements_trigger_existing_conditions(
        self, demo_layout: ACLayout, elements_with_demo: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_with_demo)
        triggered = evaluate_rules(report)
        ids = [n.trigger_rule_id for n in triggered]
        assert "existing_to_remain" in ids

    def test_triggered_notes_have_body_text(
        self, demo_layout: ACLayout, elements_with_demo: list[ACElement]
    ):
        report = analyse_layout(demo_layout, elements_with_demo)
        triggered = evaluate_rules(report)
        for note in triggered:
            assert len(note.body) > 0, f"Note '{note.section_title}' has no body text."
