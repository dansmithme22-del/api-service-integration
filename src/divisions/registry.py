"""Public registry API for division processors.

Callers should use these functions rather than reaching into
``src.divisions.base`` — the underlying storage is an implementation
detail that may move.
"""

from __future__ import annotations

from src.divisions.base import DivisionProcessor, _snapshot


def all_processors() -> list[DivisionProcessor]:
    """Every registered processor, sorted by CSI code.

    Sorting makes downstream iteration deterministic — schedule files
    and telemetry come out in the same order every run.
    """
    return [
        proc
        for _, proc in sorted(_snapshot().items(), key=lambda item: item[0])
    ]


def get_by_code(code: str) -> DivisionProcessor:
    """Look up a processor by 2-digit CSI code.

    Raises :class:`KeyError` if no processor is registered for that
    code — callers should either handle missing codes explicitly or
    check ``code in known_codes()`` first.
    """
    snap = _snapshot()
    if code not in snap:
        raise KeyError(
            f"No DivisionProcessor registered for CSI code {code!r}. "
            f"Known codes: {sorted(snap)!r}"
        )
    return snap[code]


def known_codes() -> list[str]:
    """Every registered CSI code, sorted."""
    return sorted(_snapshot())


def full_processors() -> list[DivisionProcessor]:
    """Only the launch-six full processors (excludes stubs)."""
    return [p for p in all_processors() if not p.is_stub]


def stub_processors() -> list[DivisionProcessor]:
    """Only the stub processors."""
    return [p for p in all_processors() if p.is_stub]
