"""Stage 4 — Classify contracts.

Assigns AIA layer + CSI division + subcategory to every primitive.
This is the only stage that calls an AI provider — cache hit is
tracked so downstream cost accounting works.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import SchemaVersion, StageMeta


class Classification(BaseModel):
    """One primitive's classification decision."""

    primitive_id: str
    aia_layer: str  # e.g. "A-WALL-EXST"
    csi_division: str  # e.g. "02"
    subcategory: str  # e.g. "Wall — Existing"
    confidence: float = 0.0  # 0..1
    source: Literal["stroke_weight", "geometric_pattern", "ai_vision", "text_label"]


class ClassifiedPrimitives(BaseModel):
    """Output of Stage 4. Consumed by Stage 5 (Assemble).

    Low-confidence classifications flow through per decision §13.7 —
    Stage 5 assembles them; Stage 6 flags them.
    """

    schema_version: SchemaVersion = "1.0.0"
    classifications: list[Classification] = Field(default_factory=list)
    semantic_labels: dict[str, str] = Field(default_factory=dict)
    drawing_area_norm_bbox: list[float] | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_cache_hit: bool = False
    ai_cost_usd: float = 0.0  # per §13.10 cost accounting
    meta: StageMeta
