"""Enterprise pipeline — 7-stage contract-based architecture.

See ``agent_docs/150_ENTERPRISE_PIPELINE.md`` for the full design.

Public surface kept tight on purpose. Phase A only exposes the runner
+ stage base; downstream Phase B route migrations import these and
plug in real stages.
"""

from src.pipeline.context import RunContext
from src.pipeline.runner import PipelineRunner
from src.pipeline.stage import Stage, StageError

__all__ = [
    "PipelineRunner",
    "RunContext",
    "Stage",
    "StageError",
]
