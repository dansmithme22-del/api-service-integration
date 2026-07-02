"""CSI Division 09 — Finishes.

New interior stud walls, floor finishes, ceilings, wall finishes, base.
On a renovation drawing this is the largest new-work division.

Phase A.3: identity + registration. Real assembly lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div09FinishesProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "09"
    division_name: ClassVar[str] = "Finishes"
    aia_layers: ClassVar[list[str]] = [
        "A-WALL",
        "A-FLOR-FNSH",
        "A-CLNG",
        "A-FNSH",
    ]
    typical_sheets: ClassVar[list[str]] = ["A-1.1", "A-2.1", "A-3.1"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return [
            "Mark",
            "Type",
            "Location",
            "Finish",
            "Base",
            "Ceiling",
            "Notes",
        ]
