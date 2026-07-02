"""Shared building blocks for stage contracts.

The pieces that repeat across every stage boundary — semver validation,
StageMeta (per-stage provenance the runner attaches), and lightweight
primitive/text-span models that get referenced by Extract, Normalize,
and Classify.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Semver per decision §13.6 — MAJOR.MINOR.PATCH. Pre-release / build
# metadata (1.0.0-rc1, 1.0.0+build.5) intentionally rejected: contracts
# are internal and don't need that expressiveness.
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

SchemaVersion = Annotated[
    str,
    StringConstraints(pattern=r"^\d+\.\d+\.\d+$"),
]


def is_semver(value: str) -> bool:
    """Reusable predicate for tests and validators outside Pydantic."""
    return bool(_SEMVER_PATTERN.match(value))


class StageMeta(BaseModel):
    """Per-stage provenance record.

    Every stage output carries a ``meta`` field of this shape. The runner
    populates the timing / cache fields; the stage itself may append
    warnings. Kept forward-compat: unknown fields ignored so a stage
    written against 1.1 can still be consumed by a 1.0 reader.
    """

    model_config = ConfigDict(extra="ignore")

    stage_name: str
    input_cache_key: str = ""
    output_cache_key: str = ""
    cache_hit: bool = False
    duration_ms: float | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str] = Field(default_factory=list)


class Primitive(BaseModel):
    """A single vector primitive as extracted from the PDF.

    Coordinates are in PDF user space (points, bottom-left origin, +Y up)
    unless a later stage rewrites them. Stage 3 (Normalize) may replace
    the coordinate frame.
    """

    id: str  # stable sha1 of (kind, coords, stroke_width_pt)
    kind: Literal["line", "rect", "curve"]
    coords: list[tuple[float, float]]
    stroke_width_pt: float
    fill: str | None = None


class TextSpan(BaseModel):
    """A run of text on the page with its bbox and font."""

    text: str
    bbox_pt: tuple[float, float, float, float]  # x0, y0, x1, y1
    font: str = ""
    size_pt: float = 0.0
