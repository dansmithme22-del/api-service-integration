"""Stage 6 — Validate contracts.

Runs the validation rules against the assembled model. Per decision
§13.5 severity lives on the rule, not on a global config: any rule
with ``severity="failure"`` sets ``blocks_emit=True``.

The rule framework itself lands in Phase A.6; this module only
defines the report contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.pipeline.contracts.common import SchemaVersion, StageMeta

Severity = Literal["info", "warning", "failure"]


class ValidationCheck(BaseModel):
    """A single rule evaluation result."""

    rule_id: str
    severity: Severity
    message: str
    component_ids: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Output of Stage 6. Consumed by Stage 7 (Emit).

    ``blocks_emit`` is derived from the checks: True iff any check has
    ``severity="failure"``. Callers can read it directly to short-circuit
    without walking the list.
    """

    schema_version: SchemaVersion = "1.0.0"
    checks: list[ValidationCheck] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)  # severity -> count
    overall_status: Literal["pass", "warn", "fail"] = "pass"
    blocks_emit: bool = False
    meta: StageMeta
