"""CSI Division 05 — Metals. Stub per §13.8.

Structural steel, metal deck, cold-formed framing. Stubbed at launch.
"""

from __future__ import annotations

from typing import ClassVar

from src.divisions.base import StubDivisionProcessor


class Div05MetalsStub(StubDivisionProcessor):
    division_code: ClassVar[str] = "05"
    division_name: ClassVar[str] = "Metals"
    aia_layers: ClassVar[list[str]] = ["S-COLS", "S-BEAM", "S-DECK"]
    typical_sheets: ClassVar[list[str]] = ["S-2.1", "S-3.1"]
