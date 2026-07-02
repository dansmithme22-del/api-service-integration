"""Stage 1 — Acquire contracts.

Turns a PDF path + optional page hint into a rendered, classified page
ready for extraction.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import SchemaVersion, StageMeta


class AcquireRequest(BaseModel):
    """Input to the pipeline. The Acquire stage's request contract."""

    schema_version: SchemaVersion = "1.0.0"
    pdf_path: Path
    page_index: int | None = None  # None = auto-pick floor-plan page
    render_dpi: int = 200
    project_metadata: dict = Field(default_factory=dict)


class AcquireResult(BaseModel):
    """Output of Stage 1. Consumed by Stage 2 (Extract)."""

    schema_version: SchemaVersion = "1.0.0"
    pdf_path: Path
    page_index: int
    page_size_pt: tuple[float, float]
    render_dpi: int
    png_path: Path
    is_vector: bool
    has_text: bool
    classification_reason: str
    meta: StageMeta
