"""CSI Division 06 — Wood, Plastics, and Composites.

Wood-frame walls, casework, millwork, plywood substrates. In light
commercial (vet clinics, small offices) this is the dominant partition
type.

Phase A.3: identity + registration. Real assembly (2x4/2x6 stud wall
detection from wall_weight parallel pairs) lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div06WoodPlasticsProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "06"
    division_name: ClassVar[str] = "Wood, Plastics, and Composites"
    aia_layers: ClassVar[list[str]] = ["A-WALL", "A-CASE", "A-MILL"]
    typical_sheets: ClassVar[list[str]] = ["A-2.1", "A-6.1"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return [
            "Mark",
            "Type",
            "Stud size",
            "Thickness (in)",
            "Height (ft)",
            "Sound rating",
            "Fire rating",
            "Notes",
        ]
