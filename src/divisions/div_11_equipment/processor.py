"""CSI Division 11 — Equipment.

Owner-furnished + specified equipment: exam tables, kennel banks,
autoclaves, dental chairs, restaurant hoods. Fixed equipment lives
here; movable furniture goes to Division 12.

Phase A.3: identity + registration. Real assembly (fixture recognition
against a catalog) lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div11EquipmentProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "11"
    division_name: ClassVar[str] = "Equipment"
    aia_layers: ClassVar[list[str]] = ["A-EQPM", "A-EQPM-IDEN"]
    typical_sheets: ClassVar[list[str]] = ["A-1.1", "A-6.3"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return [
            "Mark",
            "Type",
            "Manufacturer",
            "Model",
            "OFCI / CFCI",
            "Utilities",
            "Notes",
        ]
