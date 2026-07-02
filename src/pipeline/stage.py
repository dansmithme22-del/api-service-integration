"""Stage base class — every pipeline stage is a subclass of ``Stage``.

A stage takes an input Pydantic model (the previous stage's output, or
the initial Acquire input) and returns its own output Pydantic model.
Stages declare their input + output schema versions (semver per
decision §13.6) and whether they are ``deterministic`` (controls cache
eviction policy per §13.1).

The actual contract schemas land in Phase A.2 (``src/pipeline/contracts/``).
Phase A.1 only provides the abstract base + a tiny example stage so
the runner can be smoke-tested.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

from src.pipeline.context import RunContext

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class StageError(RuntimeError):
    """Raised by a stage when it cannot produce its output contract.

    Stages should raise this (not bare ``Exception``) so the runner can
    attach stage name + run_id telemetry before re-raising.
    """

    def __init__(self, stage_name: str, message: str, *, cause: Exception | None = None):
        super().__init__(f"[{stage_name}] {message}")
        self.stage_name = stage_name
        self.cause = cause


class Stage(ABC, Generic[InputT, OutputT]):
    """Abstract base for every pipeline stage.

    Subclasses MUST set:

    - ``name`` — short identifier (e.g. ``"acquire"``)
    - ``input_schema_version`` — semver string for the input contract
    - ``output_schema_version`` — semver string for the output contract

    Subclasses MAY override:

    - ``deterministic`` — defaults to ``True``. Set ``False`` for AI
      stages so the cache layer applies TTL eviction (§13.1).
    """

    name: ClassVar[str]
    input_schema_version: ClassVar[str]
    output_schema_version: ClassVar[str]
    deterministic: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Allow abstract intermediates without name (e.g. mixins). Only
        # enforce when the subclass is concrete (no abstract methods).
        if getattr(cls, "__abstractmethods__", None):
            return
        for required in ("name", "input_schema_version", "output_schema_version"):
            if not hasattr(cls, required) or getattr(cls, required) in (None, ""):
                raise TypeError(
                    f"Stage subclass {cls.__name__} must set ClassVar '{required}'"
                )

    @abstractmethod
    def run(self, data: InputT, ctx: RunContext) -> OutputT:
        """Execute the stage. Must return an instance of the output contract.

        Raise ``StageError`` for recoverable contract failures. Let
        unexpected exceptions propagate — the runner wraps them.
        """

    def cache_key(self, data: InputT) -> str:
        """Default cache key: SHA256 of the canonical JSON encoding.

        Stages with non-serialisable inputs (e.g. holding a file handle)
        should override. Most stages get this for free.
        """
        payload = data.model_dump_json().encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return f"{self.name}:{self.output_schema_version}:{digest}"
