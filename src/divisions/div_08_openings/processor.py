"""CSI Division 08 — Openings.

Doors, windows, hardware, glazing. Sourced from A-DOOR* and A-GLAZ*
layers with door swings detected as arc + line pairs.

Phase A.3: identity + registration. Real assembly (door arc detector
+ window recognition) lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div08OpeningsProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "08"
    division_name: ClassVar[str] = "Openings"
    aia_layers: ClassVar[list[str]] = [
        "A-DOOR",
        "A-DOOR-IDEN",
        "A-GLAZ",
        "A-GLAZ-IDEN",
    ]
    typical_sheets: ClassVar[list[str]] = ["A-6.1", "A-6.2", "A-8.1"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return [
            "Mark",
            "Type",
            "Width",
            "Height",
            "Leaf material",
            "Frame type",
            "Fire rating",
            "Hardware set",
            "Notes",
        ]
