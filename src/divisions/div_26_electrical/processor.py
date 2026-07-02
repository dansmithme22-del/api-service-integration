"""CSI Division 26 — Electrical. Stub per §13.8.

Panels, feeders, receptacles, switching, lighting. Stubbed at launch.
"""

from __future__ import annotations

from typing import ClassVar

from src.divisions.base import StubDivisionProcessor


class Div26ElectricalStub(StubDivisionProcessor):
    division_code: ClassVar[str] = "26"
    division_name: ClassVar[str] = "Electrical"
    aia_layers: ClassVar[list[str]] = ["E-LITE", "E-POWR", "E-PANL"]
    typical_sheets: ClassVar[list[str]] = ["E-1.1", "E-2.1"]
