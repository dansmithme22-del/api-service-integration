"""DivisionProcessor abstract base — the contract every CSI division
processor satisfies.

Concrete subclasses are auto-registered with the :class:`DivisionRegistry`
via ``__init_subclass__``. Downstream (Stage 5) walks the registry and
routes each processor its classified primitives.

Two flavors:

- :class:`DivisionProcessor` — full processor. Ships behaviour.
- :class:`StubDivisionProcessor` — placeholder for a division that
  hasn't been implemented yet (per decision §13.8, divisions 03, 05,
  07, 23, 26 ship as stubs). Emits a warning on ``assemble()`` so the
  pipeline surfaces the gap in the validation report rather than
  silently dropping primitives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Optional
from warnings import warn

from src.components.schemas import Component
from src.pipeline.contracts import ClassifiedPrimitives

# Populated by __init_subclass__. Keys are CSI codes ("02", "08", ...).
_REGISTRY: dict[str, "DivisionProcessor"] = {}


class DivisionScopeWarning(UserWarning):
    """Raised when a stub division processor is asked to assemble."""


class DivisionProcessor(ABC):
    """Base for every CSI division processor.

    Subclasses MUST set:

    - ``division_code`` — 2-digit CSI code (e.g. ``"08"``)
    - ``division_name`` — human-readable (e.g. ``"Openings"``)
    - ``aia_layers`` — AIA CAD Layer Guidelines layers this processor
      claims (e.g. ``["A-DOOR", "A-DOOR-IDEN", "A-GLAZ"]``)
    - ``typical_sheets`` — sheet identifiers where these components
      typically appear (e.g. ``["A-6.1", "A-8.1"]``)

    Concrete subclasses (i.e., those with no remaining abstract methods)
    are instantiated once and registered under their ``division_code``.
    Duplicate codes fail loudly.
    """

    division_code: ClassVar[str]
    division_name: ClassVar[str]
    aia_layers: ClassVar[list[str]] = []
    typical_sheets: ClassVar[list[str]] = []

    # Distinguishes stubs from full processors at the type level so
    # callers can log/filter without isinstance chains.
    is_stub: ClassVar[bool] = False

    # Sentinel for intermediate classes (e.g. StubDivisionProcessor)
    # that provide behaviour but are NOT themselves a division. Direct
    # subclasses set this back to False (default) so they register.
    _abstract_intermediate: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            # Intermediate ABC — don't try to register.
            return
        if cls.__dict__.get("_abstract_intermediate", False):
            # Explicit opt-out: this class provides behaviour to its
            # subclasses but doesn't itself claim a CSI code.
            return
        for required in ("division_code", "division_name"):
            if not hasattr(cls, required) or getattr(cls, required) in (None, ""):
                raise TypeError(
                    f"DivisionProcessor {cls.__name__} must set ClassVar "
                    f"'{required}'"
                )
        instance = cls()
        code = instance.division_code
        if code in _REGISTRY:
            existing = type(_REGISTRY[code]).__name__
            raise RuntimeError(
                f"DivisionProcessor for code {code!r} already registered "
                f"({existing}); cannot register {cls.__name__}"
            )
        _REGISTRY[code] = instance

    @abstractmethod
    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        """Turn classified primitives into buildable Components.

        Full processors implement real assembly logic; stubs return an
        empty list + emit a :class:`DivisionScopeWarning`.
        """

    def schedule_columns(self) -> list[str]:
        """Columns in this division's schedule CSV.

        Defaults to the common set (Mark, Type, Notes). Divisions
        override to add typed columns (Wall thickness, Door width...).
        """
        return ["Mark", "Type", "Notes"]

    def row_for_component(self, component: Component) -> dict:
        """Render one component as a schedule row.

        Default implementation reads the fields present on the base
        ``Component``. Subclasses override to pull typed fields off
        their component subtype.
        """
        return {
            "Mark": component.mark,
            "Type": component.name or component.kind.value,
            "Notes": component.notes,
        }


class StubDivisionProcessor(DivisionProcessor):
    """Placeholder for a not-yet-implemented division.

    Emits a :class:`DivisionScopeWarning` on ``assemble()`` and returns
    an empty component list. Subclasses only need to set the class-
    level identity fields.
    """

    is_stub: ClassVar[bool] = True
    _abstract_intermediate: ClassVar[bool] = True

    def assemble(self, classified: ClassifiedPrimitives) -> list[Component]:
        # Show up in stderr AND in the pipeline validation report — the
        # runner passes a StageMeta warnings list into ctx.extras so
        # Stage 6 can pick it up without side channels.
        message = (
            f"Division {self.division_code} ({self.division_name}) is a stub — "
            f"any primitives classified for this division will be dropped."
        )
        warn(message, DivisionScopeWarning, stacklevel=2)
        return []


def _lookup(code: str) -> Optional[DivisionProcessor]:
    """Read-only accessor for the module-level registry.

    Public callers should go through :mod:`src.divisions.registry`.
    """
    return _REGISTRY.get(code)


def _clear() -> None:
    """Clear the registry — tests only. Do not call in production."""
    _REGISTRY.clear()


def _snapshot() -> dict[str, DivisionProcessor]:
    """Copy of the registry contents. Tests only."""
    return dict(_REGISTRY)
