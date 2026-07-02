"""CSI Division 23 — HVAC. Stub per §13.8.

Air handlers, ductwork, diffusers, thermostats, exhaust. Consumer of
mep-mechanical-hvac skill guidance when implemented.
"""

from __future__ import annotations

from typing import ClassVar

from src.divisions.base import StubDivisionProcessor


class Div23HVACStub(StubDivisionProcessor):
    division_code: ClassVar[str] = "23"
    division_name: ClassVar[str] = "Heating, Ventilating, and Air Conditioning"
    aia_layers: ClassVar[list[str]] = ["M-DUCT", "M-EQPM", "M-DIFF"]
    typical_sheets: ClassVar[list[str]] = ["M-1.1", "M-2.1"]
