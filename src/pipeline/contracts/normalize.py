"""Stage 3 — Normalize contracts.

Turns raw primitives into clean geometry with a real-world scale.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import Primitive, SchemaVersion, StageMeta


class CalibrationResult(BaseModel):
    """The linear transform between drawing units and real-world inches.

    ``inches_per_norm`` is what to multiply a normalized-coordinate delta
    by to get inches. ``source`` records how we discovered it, and
    ``confidence`` is 0..1 (1.0 = extracted from a dimension callout that
    matched geometry to within 1%; 0.0 = fell back to default).
    """

    inches_per_norm: float
    source: Literal["scale_text", "dim_callout", "default", "manual_override"]
    dim_text: str = ""
    confidence: float = 0.0


class NormalizedGeometry(BaseModel):
    """Output of Stage 3. Consumed by Stage 4 (Classify).

    Primitives are partitioned by stroke class (wall_weight / secondary /
    annotation / patterning) as inferred from the stroke histogram in
    the ExtractResult.
    """

    schema_version: SchemaVersion = "1.0.0"
    primitives_by_stroke_class: dict[str, list[Primitive]] = Field(default_factory=dict)
    calibration: CalibrationResult
    page_size_pt: tuple[float, float]
    page_size_in: tuple[float, float]
    drawing_area_norm_bbox: list[float] | None = None
    meta: StageMeta
