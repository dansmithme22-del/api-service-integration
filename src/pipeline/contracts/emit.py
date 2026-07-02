"""Stage 7 — Emit contracts.

Generates every output artifact for the run. Each artifact is described
by kind + path + sha256 so downstream reproducibility checks are cheap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import SchemaVersion, StageMeta

ArtifactKind = Literal[
    "schedule_csv",
    "schedule_json",
    "svg_lossless",
    "svg_layered",
    "svg_components",
    "review_html",
    "archicad_tape",
    "plan_json",
]


class Artifact(BaseModel):
    """One emitted file — path, kind, sha256, size."""

    path: Path
    kind: ArtifactKind
    sha256: str
    size_bytes: int


class EmitResult(BaseModel):
    """Final pipeline output. Terminal — no stage consumes this."""

    schema_version: SchemaVersion = "1.0.0"
    artifacts: list[Artifact] = Field(default_factory=list)
    output_dir: Path
    meta: StageMeta
