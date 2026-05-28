"""PDF -> PlanGraph ingest layer.

Layer 0 of the pipeline: turn a reference PDF (vector or raster) into a
structured PlanGraph that the build/ layer can then materialise as Archicad
elements.

Top-level entry points:

    from src.ingest import ingest_pdf

    plan = ingest_pdf("plan.pdf")
    # -> PlanGraph
"""

from .plan_model import (
    AccuracyCheck,
    AccuracyReport,
    Annotation,
    DimensionCallout,
    Fixture,
    FixtureKind,
    Opening,
    OpeningKind,
    PageMeta,
    PlanGraph,
    Room,
    Wall,
    WallStatus,
)
from .runner import ingest_pdf

__all__ = [
    "ingest_pdf",
    "AccuracyCheck",
    "AccuracyReport",
    "Annotation",
    "DimensionCallout",
    "Fixture",
    "FixtureKind",
    "Opening",
    "OpeningKind",
    "PageMeta",
    "PlanGraph",
    "Room",
    "Wall",
    "WallStatus",
]
