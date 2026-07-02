"""PipelineRunner — walks an ordered list of Stages, sequentially.

Per decision §13.2, launch ships sequential-only. A ``--parallel`` flag
will arrive later once profiling justifies it; the runner contract is
stable so that change won't break callers.

Phase A.1 wires only the stage walk. Cache hooks (A.4), telemetry hooks
(A.5), and cost-cap enforcement (A.5) attach to the same ``before_stage``
/ ``after_stage`` extension points.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from src.pipeline.context import RunContext
from src.pipeline.stage import Stage, StageError


class PipelineRunner:
    """Run a fixed sequence of stages end-to-end.

    Parameters
    ----------
    stages
        Ordered sequence. The output of stage ``i`` must satisfy the
        input contract of stage ``i+1``. Contract validation happens
        inside each stage (Pydantic auto-validates on construction).
    """

    def __init__(self, stages: Sequence[Stage]):
        if not stages:
            raise ValueError("PipelineRunner requires at least one stage")
        self.stages: tuple[Stage, ...] = tuple(stages)

    def run(self, initial_input: BaseModel, ctx: RunContext | None = None) -> BaseModel:
        """Execute the pipeline. Returns the final stage's output.

        Notes
        -----
        - A fresh ``RunContext`` is created if the caller doesn't pass
          one. Tests typically pass their own to control ``runs_root``.
        - ``StageError`` from any stage propagates with stage name +
          run_id attached.
        - Unexpected exceptions are wrapped in ``StageError`` so callers
          always get a consistent failure shape.
        """
        ctx = ctx or RunContext()
        data: BaseModel = initial_input

        for stage in self.stages:
            try:
                data = stage.run(data, ctx)
            except StageError:
                raise
            except Exception as exc:  # noqa: BLE001 — wrap for uniform shape
                raise StageError(
                    stage.name,
                    f"unexpected error in run_id={ctx.run_id}: {exc!r}",
                    cause=exc,
                ) from exc

        return data
