"""CSI Division 03 — Concrete. Stub per §13.8.

Slabs, columns, foundations, walls. Stubbed at launch because vet-
clinic renovation drawings rarely carry concrete detail; when a
project needs it we implement here.
"""

from __future__ import annotations

from typing import ClassVar

from src.divisions.base import StubDivisionProcessor


class Div03ConcreteStub(StubDivisionProcessor):
    division_code: ClassVar[str] = "03"
    division_name: ClassVar[str] = "Concrete"
    aia_layers: ClassVar[list[str]] = ["S-CONC", "S-SLAB", "S-FNDN"]
    typical_sheets: ClassVar[list[str]] = ["S-1.1", "S-2.1"]
