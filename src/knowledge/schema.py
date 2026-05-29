"""Pydantic schemas for the knowledge store.

A KnowledgeItem is the smallest indexable unit. Every item carries:
  * a KIND (csi_division, abbreviation, symbol, ibc_use_group, …)
  * a LAYER (csi / reference / ibc / office) — controls visibility
  * a TEXT (what gets embedded)
  * structured payload for the consuming code

Permit-mode is the user-facing toggle:
  * permit_mode = False → CSI + reference + office are visible
  * permit_mode = True  → ALL layers including IBC are visible
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeLayer(str, Enum):
    """Which layer of the knowledge stack an item belongs to."""
    CSI = "csi"                  # CSI MasterFormat (under-the-hood logic)
    DRAFTING = "drafting"        # AIA/NCS layer standards, scales, line types
    REFERENCE = "reference"      # Anne Arundel + other gold-standard CD sets
    IBC = "ibc"                  # Building code — only visible in permit mode
    OFFICE = "office"            # Firm-specific patterns (Vetcor, etc.)


class KnowledgeKind(str, Enum):
    """What an item describes."""
    CSI_DIVISION = "csi_division"
    CSI_SECTION = "csi_section"
    ABBREVIATION = "abbreviation"
    SYMBOL = "symbol"
    SHEET_TEMPLATE = "sheet_template"
    SCHEDULE_TEMPLATE = "schedule_template"
    IBC_USE_GROUP = "ibc_use_group"
    IBC_EGRESS_RULE = "ibc_egress_rule"
    IBC_FIRE_RATING = "ibc_fire_rating"
    ROOM_TYPE = "room_type"
    FIXTURE_TYPE = "fixture_type"
    OPENING_TYPE = "opening_type"
    WALL_ASSEMBLY = "wall_assembly"
    REFERENCE_PATTERN = "reference_pattern"
    OFFICE_PATTERN = "office_pattern"
    # Drafting standards (AIA/NCS/ISO 128)
    AIA_LAYER = "aia_layer"
    LINE_TYPE = "line_type"
    LINE_WEIGHT = "line_weight"
    ARCH_SCALE = "arch_scale"
    SHEET_TYPE_DIGIT = "sheet_type_digit"
    DISCIPLINE_CODE = "discipline_code"
    STATUS_CODE = "status_code"


class KnowledgeItem(BaseModel):
    """One indexable knowledge item."""
    id: str                       # stable id, e.g. "csi:08" or "ibc:A-3"
    kind: KnowledgeKind
    layer: KnowledgeLayer
    name: str                     # short label, e.g. "Openings"
    description: str = ""         # longer text used as the embedding source
    code: str = ""                # e.g. "08", "A-3", "ACT"
    csi_division: str = ""        # which CSI division it relates to ("" if N/A)
    sheets: list[str] = Field(default_factory=list)
                                  # CD sheet codes where it appears
    payload: dict[str, Any] = Field(default_factory=dict)
                                  # structured data the caller can use
    permit_only: bool = False     # if True, hidden unless permit_mode=True
    aliases: list[str] = Field(default_factory=list)
                                  # alternate names included in embedding text

    def embedding_text(self) -> str:
        """Compose the text that gets embedded for similarity search."""
        chunks = [self.name]
        if self.code:
            chunks.append(f"[{self.code}]")
        if self.aliases:
            chunks.append("aka " + ", ".join(self.aliases))
        if self.description:
            chunks.append(self.description)
        return " — ".join(chunks)


class SearchResult(BaseModel):
    item: KnowledgeItem
    score: float                  # higher = more similar (cosine)
