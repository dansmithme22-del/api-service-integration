"""Stage 5 — Assemble contracts.

Groups classified primitives into buildable Components, organized by
CSI division. Components use the existing ``src.components.schemas``
Component model — Phase A doesn't fork the component surface.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.components.schemas import Component
from src.pipeline.contracts.common import Primitive, SchemaVersion, StageMeta


class AssemblyResult(BaseModel):
    """Output of Stage 5. Consumed by Stage 6 (Validate) and Stage 7 (Emit).

    ``components_by_division`` keys are CSI division codes ("02", "06",
    "08", …). Divisions with no components can be absent — presence is
    not required, so a stub division registry is a valid state.
    """

    schema_version: SchemaVersion = "1.0.0"
    components_by_division: dict[str, list[Component]] = Field(default_factory=dict)
    orphan_primitives: list[Primitive] = Field(default_factory=list)
    coverage: float = 0.0  # primitives_used / primitives_total, 0..1
    meta: StageMeta
