"""Layout Annotation Automation — Pydantic data models.

These models are the shared contract between the Extract, Decide, and Apply
layers.  Everything serialises to / from JSON so you can inspect intermediate
artefacts at every stage.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Phase(str, Enum):
    """Standard renovation phases.  Extend as needed."""
    EXISTING = "Existing"
    DEMOLITION = "Demolition"
    NEW_CONSTRUCTION = "New Construction"


class Discipline(str, Enum):
    """Sheet discipline derived from the sheet-number prefix."""
    ARCHITECTURAL = "Architectural"
    STRUCTURAL = "Structural"
    MECHANICAL = "Mechanical"
    PLUMBING = "Plumbing"
    ELECTRICAL = "Electrical"
    FIRE_PROTECTION = "Fire Protection"
    LANDSCAPE = "Landscape"
    CIVIL = "Civil"
    GENERAL = "General"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Archicad-sourced data (Extract layer output)
# ---------------------------------------------------------------------------

class ACElement(BaseModel):
    """A single Archicad element as read from the JSON API."""
    guid: str
    element_type: str                          # "Wall", "Column", "Object", …
    layer_name: str = ""
    story_name: str = ""
    renovation_status: Optional[Phase] = None  # None when unable to read
    classification: str = ""                   # e.g. "Plumbing Fixture"
    properties: dict[str, Any] = Field(default_factory=dict)


class ACDrawing(BaseModel):
    """A Drawing element placed on a Layout."""
    guid: str
    name: str = ""
    source_view_id: str = ""                   # navigator item GUID of the source view
    source_view_path: str = ""                 # human-readable path in navigator


class ACLayout(BaseModel):
    """A Layout (sheet) from the navigator tree."""
    guid: str
    layout_name: str                           # "A-101 - FIRST FLOOR PLAN"
    sheet_id: str = ""                         # "A-101"  (parsed from name)
    discipline: Discipline = Discipline.UNKNOWN
    master_layout_name: str = ""
    drawings: list[ACDrawing] = Field(default_factory=list)


class ModelSnapshot(BaseModel):
    """Everything the Extract layer produces in one pass."""
    model_config = {"arbitrary_types_allowed": True}

    timestamp: datetime = Field(default_factory=datetime.now)
    project_name: str = ""
    elements: list[ACElement] = Field(default_factory=list)
    layouts: list[ACLayout] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Notes data model (Decide layer output)
# ---------------------------------------------------------------------------

class NoteEntry(BaseModel):
    """One triggered note section (e.g. "Demolition Notes")."""
    trigger_rule_id: str          # id from rules.json that fired
    section_title: str            # "DEMOLITION NOTES"
    body: list[str]               # ordered lines of note text


class SheetNotes(BaseModel):
    """Complete annotation payload for a single layout."""
    sheet_id: str                                     # "A-101"
    sheet_name: str = ""
    discipline: Discipline = Discipline.UNKNOWN
    general_notes: list[str] = Field(default_factory=list)
    code_notes: list[str] = Field(default_factory=list)
    phase_notes: dict[str, list[str]] = Field(default_factory=dict)
    element_driven_notes: list[NoteEntry] = Field(default_factory=list)
    scope_notes: list[str] = Field(default_factory=list)
    manual_notes: list[str] = Field(default_factory=list)

    def render_flat_text(self, separator: str = "\n") -> str:
        """Collapse all notes into a single string for property injection."""
        sections: list[str] = []

        if self.general_notes:
            sections.append("GENERAL NOTES")
            sections.extend(self.general_notes)
            sections.append("")

        if self.code_notes:
            sections.append("CODE NOTES")
            sections.extend(self.code_notes)
            sections.append("")

        for entry in self.element_driven_notes:
            sections.append(entry.section_title)
            sections.extend(entry.body)
            sections.append("")

        for phase_key, lines in self.phase_notes.items():
            sections.append(f"{phase_key.upper()} NOTES")
            sections.extend(lines)
            sections.append("")

        if self.scope_notes:
            sections.append("SCOPE OF WORK")
            sections.extend(self.scope_notes)
            sections.append("")

        if self.manual_notes:
            sections.append("PROJECT-SPECIFIC NOTES")
            sections.extend(self.manual_notes)
            sections.append("")

        return separator.join(sections)


class ProjectNotesOutput(BaseModel):
    """Top-level artefact: all notes for every layout in the project."""
    project_name: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)
    global_general_notes: list[str] = Field(default_factory=list)
    global_code_notes: list[str] = Field(default_factory=list)
    sheets: list[SheetNotes] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Prefix → Discipline mapping (loaded from config at runtime, but provide a
# hard-coded default so the model is self-contained for testing).
_PREFIX_MAP: dict[str, Discipline] = {
    "A": Discipline.ARCHITECTURAL,
    "S": Discipline.STRUCTURAL,
    "M": Discipline.MECHANICAL,
    "P": Discipline.PLUMBING,
    "E": Discipline.ELECTRICAL,
    "FP": Discipline.FIRE_PROTECTION,
    "L": Discipline.LANDSCAPE,
    "C": Discipline.CIVIL,
    "G": Discipline.GENERAL,
}

_SHEET_RE = re.compile(r"^(?P<discipline>[A-Z]+)-(?P<number>\d+)")


def parse_sheet_id(raw_name: str) -> tuple[str, Discipline]:
    """Extract sheet_id and discipline from a layout name like 'A-101 - FIRST FLOOR PLAN'.

    Returns (sheet_id, Discipline).  Falls back to (raw_name, UNKNOWN).
    """
    m = _SHEET_RE.match(raw_name.strip())
    if not m:
        return raw_name.strip(), Discipline.UNKNOWN
    sheet_id = f"{m.group('discipline')}-{m.group('number')}"
    discipline = _PREFIX_MAP.get(m.group("discipline"), Discipline.UNKNOWN)
    return sheet_id, discipline
