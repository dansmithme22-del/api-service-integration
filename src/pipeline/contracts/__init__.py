"""Stage contract Pydantic schemas — one module per stage boundary.

Each stage's input is the previous stage's output. Import from this
package rather than from the individual modules so the public surface
is easy to survey.
"""

from src.pipeline.contracts.acquire import AcquireRequest, AcquireResult
from src.pipeline.contracts.assemble import AssemblyResult
from src.pipeline.contracts.classify import Classification, ClassifiedPrimitives
from src.pipeline.contracts.common import (
    Primitive,
    SchemaVersion,
    StageMeta,
    TextSpan,
    is_semver,
)
from src.pipeline.contracts.emit import Artifact, ArtifactKind, EmitResult
from src.pipeline.contracts.normalize import CalibrationResult, NormalizedGeometry
from src.pipeline.contracts.validate import Severity, ValidationCheck, ValidationReport

__all__ = [
    "AcquireRequest",
    "AcquireResult",
    "Artifact",
    "ArtifactKind",
    "AssemblyResult",
    "CalibrationResult",
    "Classification",
    "ClassifiedPrimitives",
    "EmitResult",
    "NormalizedGeometry",
    "Primitive",
    "SchemaVersion",
    "Severity",
    "StageMeta",
    "TextSpan",
    "ValidationCheck",
    "ValidationReport",
    "is_semver",
]
