"""CSI Division 02 — Existing Conditions.

Demolition + existing-to-remain construction. Scope typically includes
existing walls, existing fixtures, salvage/protection scope.

Phase A.3: identity + registration. Real assembly (existing wall pair
detection) lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div02ExistingConditionsProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "02"
    division_name: ClassVar[str] = "Existing Conditions"
    aia_layers: ClassVar[list[str]] = ["A-WALL-EXST", "A-FLOR-EXST", "A-CLNG-EXST"]
    typical_sheets: ClassVar[list[str]] = ["A-0.1", "AD-1.1"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return ["Mark", "Type", "Thickness (in)", "Height (ft)", "Status", "Notes"]
