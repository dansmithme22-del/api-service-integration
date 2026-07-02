"""CSI Division 22 — Plumbing.

Fixtures (water closets, lavatories, sinks, floor drains), rough-in
locations, trap primers. The architect's coordination surface with
the plumbing engineer.

Phase A.3: identity + registration. Real assembly (fixture recognition
from A-PLMB* layers + fixture-unit lookup) lands in Phase B.
"""

from __future__ import annotations

from typing import ClassVar

from src.components.schemas import Component
from src.divisions.base import DivisionProcessor
from src.pipeline.contracts import ClassifiedPrimitives


class Div22PlumbingProcessor(DivisionProcessor):
    division_code: ClassVar[str] = "22"
    division_name: ClassVar[str] = "Plumbing"
    aia_layers: ClassVar[list[str]] = ["A-PLMB", "A-PLMB-FIXT", "P-FIXT"]
    typical_sheets: ClassVar[list[str]] = ["P-1.1", "P-2.1"]

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        return []

    def schedule_columns(self) -> list[str]:
        return [
            "Mark",
            "Fixture type",
            "Trap size",
            "DFU",
            "WSFU (hot)",
            "WSFU (cold)",
            "Notes",
        ]
