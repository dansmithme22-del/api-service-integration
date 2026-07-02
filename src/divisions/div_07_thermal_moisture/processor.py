"""CSI Division 07 — Thermal and Moisture Protection. Stub per §13.8.

Roofing, insulation, sealants, waterproofing, air/vapor barriers.
Stubbed at launch.
"""

from __future__ import annotations

from typing import ClassVar

from src.divisions.base import StubDivisionProcessor


class Div07ThermalMoistureStub(StubDivisionProcessor):
    division_code: ClassVar[str] = "07"
    division_name: ClassVar[str] = "Thermal and Moisture Protection"
    aia_layers: ClassVar[list[str]] = ["A-ROOF", "A-INSL"]
    typical_sheets: ClassVar[list[str]] = ["A-4.1", "A-7.1"]
