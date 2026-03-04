"""Tests for the note builder (no Archicad connection needed)."""

from __future__ import annotations

import json

import pytest

from src.models.data_model import (
    ACElement,
    ACLayout,
    Discipline,
    Phase,
    ProjectNotesOutput,
    SheetNotes,
    parse_sheet_id,
)
from src.decide.phase_analyzer import analyse_layout, analyse_all_layouts
from src.decide.note_builder import build_sheet_notes, build_all_notes


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_layouts() -> list[ACLayout]:
    return [
        ACLayout(guid="lay-1", layout_name="A-101 - DEMO PLAN",
                 sheet_id="A-101", discipline=Discipline.ARCHITECTURAL),
        ACLayout(guid="lay-2", layout_name="A-102 - NEW WORK PLAN",
                 sheet_id="A-102", discipline=Discipline.ARCHITECTURAL),
    ]


@pytest.fixture
def sample_elements() -> list[ACElement]:
    return [
        ACElement(guid="e1", element_type="Wall", renovation_status=Phase.DEMOLITION),
        ACElement(guid="e2", element_type="Wall", renovation_status=Phase.EXISTING),
        ACElement(guid="e3", element_type="Wall", renovation_status=Phase.NEW_CONSTRUCTION),
        ACElement(guid="e4", element_type="Column", renovation_status=Phase.NEW_CONSTRUCTION),
    ]


# ── Tests ─────────────────────────────────────────────────────────────

class TestNoteBuilder:
    def test_build_sheet_notes_returns_model(
        self, sample_layouts, sample_elements
    ):
        layout = sample_layouts[0]
        report = analyse_layout(layout, sample_elements)
        sn = build_sheet_notes(layout, report)
        assert isinstance(sn, SheetNotes)
        assert sn.sheet_id == "A-101"

    def test_sheet_notes_has_general_notes(
        self, sample_layouts, sample_elements
    ):
        layout = sample_layouts[0]
        report = analyse_layout(layout, sample_elements)
        sn = build_sheet_notes(layout, report)
        assert len(sn.general_notes) > 0

    def test_build_all_notes_covers_all_layouts(
        self, sample_layouts, sample_elements
    ):
        reports = analyse_all_layouts(sample_layouts, sample_elements)
        output = build_all_notes(sample_layouts, reports, project_name="Test")
        assert isinstance(output, ProjectNotesOutput)
        assert len(output.sheets) == len(sample_layouts)

    def test_flat_text_render(self, sample_layouts, sample_elements):
        layout = sample_layouts[0]
        report = analyse_layout(layout, sample_elements)
        sn = build_sheet_notes(layout, report)
        text = sn.render_flat_text()
        assert "GENERAL NOTES" in text

    def test_serialises_to_json(self, sample_layouts, sample_elements):
        reports = analyse_all_layouts(sample_layouts, sample_elements)
        output = build_all_notes(sample_layouts, reports)
        payload = output.model_dump(mode="json")
        json_str = json.dumps(payload, default=str)
        assert len(json_str) > 100


class TestParseSheetId:
    def test_standard_prefix(self):
        sid, disc = parse_sheet_id("A-101 - FIRST FLOOR PLAN")
        assert sid == "A-101"
        assert disc == Discipline.ARCHITECTURAL

    def test_plumbing(self):
        sid, disc = parse_sheet_id("P-201")
        assert sid == "P-201"
        assert disc == Discipline.PLUMBING

    def test_unknown_prefix(self):
        sid, disc = parse_sheet_id("X-999")
        assert sid == "X-999"
        assert disc == Discipline.UNKNOWN

    def test_non_matching(self):
        sid, disc = parse_sheet_id("Some Random Name")
        assert disc == Discipline.UNKNOWN
