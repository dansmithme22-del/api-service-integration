"""Stage 2 — Extract contracts.

Losslessly pulls every primitive from the PDF page with stroke metadata.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import Primitive, SchemaVersion, StageMeta, TextSpan


class ExtractResult(BaseModel):
    """Output of Stage 2. Consumed by Stage 3 (Normalize).

    For large extracts (>10K primitives) the primitives array may be
    sidelined to a Parquet file and this JSON carries the counts only.
    """

    schema_version: SchemaVersion = "1.0.0"
    page_size_pt: tuple[float, float]
    primitives: list[Primitive] = Field(default_factory=list)
    text_spans: list[TextSpan] = Field(default_factory=list)
    stroke_histogram: dict[float, int] = Field(default_factory=dict)
    primitives_parquet_path: Path | None = None
    meta: StageMeta
