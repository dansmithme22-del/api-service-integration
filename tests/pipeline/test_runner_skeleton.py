"""Phase A.1 smoke tests for src.pipeline.

Confirms the skeleton wires together: Stage subclasses can declare a
contract, PipelineRunner walks them in order, RunContext flows through,
and exceptions are wrapped consistently.

Real contract + integration tests land in Phase A.7.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from src.pipeline import PipelineRunner, RunContext, Stage, StageError


# --- Fixture contracts ----------------------------------------------------


class _Seed(BaseModel):
    n: int


class _Doubled(BaseModel):
    n: int
    history: list[str] = []


class _Squared(BaseModel):
    n: int
    history: list[str] = []


# --- Fixture stages -------------------------------------------------------


class _DoubleStage(Stage[_Seed, _Doubled]):
    name = "double"
    input_schema_version = "1.0.0"
    output_schema_version = "1.0.0"

    def run(self, data: _Seed, ctx: RunContext) -> _Doubled:
        return _Doubled(n=data.n * 2, history=[f"double@{ctx.run_id}"])


class _SquareStage(Stage[_Doubled, _Squared]):
    name = "square"
    input_schema_version = "1.0.0"
    output_schema_version = "1.0.0"

    def run(self, data: _Doubled, ctx: RunContext) -> _Squared:
        return _Squared(n=data.n * data.n, history=[*data.history, f"square@{ctx.run_id}"])


class _BoomStage(Stage[_Seed, _Doubled]):
    name = "boom"
    input_schema_version = "1.0.0"
    output_schema_version = "1.0.0"

    def run(self, data: _Seed, ctx: RunContext) -> _Doubled:
        raise ValueError("intentional test failure")


# --- Tests ----------------------------------------------------------------


def test_runner_walks_stages_in_order(tmp_path: Path) -> None:
    ctx = RunContext(runs_root=tmp_path)
    runner = PipelineRunner([_DoubleStage(), _SquareStage()])

    result = runner.run(_Seed(n=3), ctx=ctx)

    assert isinstance(result, _Squared)
    assert result.n == 36  # (3 * 2) ** 2
    assert result.history == [f"double@{ctx.run_id}", f"square@{ctx.run_id}"]


def test_runner_creates_fresh_context_when_none_passed() -> None:
    runner = PipelineRunner([_DoubleStage()])
    result = runner.run(_Seed(n=5))
    assert result.n == 10  # type: ignore[attr-defined]


def test_runner_rejects_empty_stage_list() -> None:
    with pytest.raises(ValueError, match="at least one stage"):
        PipelineRunner([])


def test_runner_wraps_unexpected_exceptions_as_stage_error(tmp_path: Path) -> None:
    ctx = RunContext(runs_root=tmp_path)
    runner = PipelineRunner([_BoomStage()])

    with pytest.raises(StageError) as excinfo:
        runner.run(_Seed(n=1), ctx=ctx)

    assert excinfo.value.stage_name == "boom"
    assert isinstance(excinfo.value.cause, ValueError)
    assert ctx.run_id in str(excinfo.value)


def test_stage_subclass_must_set_required_class_vars() -> None:
    with pytest.raises(TypeError, match="must set ClassVar"):
        class _Incomplete(Stage[_Seed, _Doubled]):  # missing name + versions
            def run(self, data: _Seed, ctx: RunContext) -> _Doubled:
                return _Doubled(n=0)


def test_cache_key_is_stable_for_identical_input() -> None:
    stage = _DoubleStage()
    k1 = stage.cache_key(_Seed(n=42))
    k2 = stage.cache_key(_Seed(n=42))
    k3 = stage.cache_key(_Seed(n=43))
    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("double:1.0.0:")


def test_run_context_creates_run_dir_lazily(tmp_path: Path) -> None:
    ctx = RunContext(runs_root=tmp_path)
    assert not ctx.run_dir.exists()
    created = ctx.ensure_run_dir()
    assert created.exists()
    assert created == tmp_path / ctx.run_id
    # idempotent
    ctx.ensure_run_dir()
