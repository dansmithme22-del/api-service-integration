"""Phase A.3 tests for src.divisions.

Covers:

- All 11 divisions register on import.
- Launch-six are full (is_stub=False); the rest are stubs.
- Registry accessors (all_processors, full_processors, stub_processors,
  get_by_code, known_codes) behave correctly.
- Stub processors emit DivisionScopeWarning on assemble().
- Duplicate CSI code registration fails loudly.
- Base __init_subclass__ enforces required ClassVars.
"""

from __future__ import annotations

import warnings

import pytest

# Importing src.divisions triggers auto-registration of every processor.
import src.divisions
from src.divisions.base import DivisionProcessor, DivisionScopeWarning
from src.divisions.registry import (
    all_processors,
    full_processors,
    get_by_code,
    known_codes,
    stub_processors,
)

_ = src.divisions  # silence linters

LAUNCH_FULL_CODES = {"02", "06", "08", "09", "11", "22"}
LAUNCH_STUB_CODES = {"03", "05", "07", "23", "26"}
ALL_LAUNCH_CODES = LAUNCH_FULL_CODES | LAUNCH_STUB_CODES


def test_all_eleven_launch_divisions_registered() -> None:
    codes = set(known_codes())
    assert codes == ALL_LAUNCH_CODES, (
        f"Registry drift: expected {ALL_LAUNCH_CODES}, got {codes}"
    )


def test_full_processors_are_the_launch_six() -> None:
    full_codes = {p.division_code for p in full_processors()}
    assert full_codes == LAUNCH_FULL_CODES


def test_stub_processors_are_the_launch_five() -> None:
    stub_codes = {p.division_code for p in stub_processors()}
    assert stub_codes == LAUNCH_STUB_CODES


def test_all_processors_sorted_by_code() -> None:
    codes = [p.division_code for p in all_processors()]
    assert codes == sorted(codes)


@pytest.mark.parametrize("code", sorted(ALL_LAUNCH_CODES))
def test_get_by_code_finds_each_launch_division(code: str) -> None:
    proc = get_by_code(code)
    assert proc.division_code == code
    assert proc.division_name  # non-empty


def test_get_by_code_missing_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="No DivisionProcessor registered"):
        get_by_code("99")


def test_stub_processor_emits_warning_on_assemble() -> None:
    from src.pipeline.contracts import ClassifiedPrimitives, StageMeta

    stub = get_by_code("23")  # HVAC
    assert stub.is_stub is True

    empty_classified = ClassifiedPrimitives(meta=StageMeta(stage_name="classify"))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = stub.assemble(empty_classified)

    assert result == []
    assert len(caught) == 1
    assert issubclass(caught[0].category, DivisionScopeWarning)
    assert "Division 23" in str(caught[0].message)


def test_full_processor_does_not_warn_on_empty_input() -> None:
    from src.pipeline.contracts import ClassifiedPrimitives, StageMeta

    full = get_by_code("08")  # Openings
    assert full.is_stub is False

    empty_classified = ClassifiedPrimitives(meta=StageMeta(stage_name="classify"))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = full.assemble(empty_classified)

    assert result == []
    assert not any(issubclass(w.category, DivisionScopeWarning) for w in caught)


def test_launch_processors_declare_typed_schedule_columns() -> None:
    # Divisions that don't override schedule_columns should still work,
    # but each launch-six division has a real column set per its trade.
    for code in LAUNCH_FULL_CODES:
        cols = get_by_code(code).schedule_columns()
        assert "Mark" in cols
        assert len(cols) >= 3


def test_duplicate_registration_fails_loudly() -> None:
    """A second class claiming code '08' must raise on definition."""
    with pytest.raises(RuntimeError, match="already registered"):
        class DuplicateDiv08(DivisionProcessor):  # noqa: N801
            division_code = "08"
            division_name = "Openings (duplicate)"

            def assemble(self, classified):  # type: ignore[no-untyped-def]
                return []


def test_missing_class_var_fails_at_definition() -> None:
    with pytest.raises(TypeError, match="must set ClassVar 'division_code'"):
        class BrokenNoCode(DivisionProcessor):  # noqa: N801
            division_name = "Nowhere"

            def assemble(self, classified):  # type: ignore[no-untyped-def]
                return []
