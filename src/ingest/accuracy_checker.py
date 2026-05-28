"""Verify a PlanGraph's geometry is internally consistent with its callouts.

The vision parser asks Gemini to report every visible dimension callout along
with the two endpoints the dimension line spans. This module measures those
spans against the geometry the same response produced — if they don't match,
the model's coordinates are inconsistent and the plan should not be trusted
for BIM ingest until the user reviews / re-runs.

Three accuracy bands per check:
  * **pass**  — |delta| <= 2% (within a typical drafting fudge)
  * **warn**  — |delta| <= 10% (visually wrong but recognisable)
  * **fail**  — |delta| > 10% (model contradicted itself badly)

Aggregate verdict on the whole plan:
  * `pass` if median pct error <= 2% and zero fails
  * `warn` if median pct error <= 10% and fails <= 10% of checks
  * `fail` otherwise
"""

from __future__ import annotations

import logging
import math
import statistics

from .plan_model import (
    AccuracyCheck,
    AccuracyReport,
    DimensionCallout,
    PlanGraph,
)

logger = logging.getLogger(__name__)


PASS_PCT = 2.0
WARN_PCT = 10.0


def check_plan_accuracy(plan: PlanGraph) -> AccuracyReport:
    """Run dimension-vs-geometry checks; attach the report to the plan in place."""
    report = AccuracyReport()

    if not plan.dimension_callouts:
        report.overall_status = "unknown"
        report.notes.append(
            "No dimension callouts reported by the parser — accuracy cannot "
            "be verified. Re-run with a higher DPI, a clearer source PDF, or "
            "a reference PDF (e.g. Matterport)."
        )
        plan.accuracy_report = report
        return report

    pct_errors: list[float] = []

    for dc in plan.dimension_callouts:
        check = _check_one(dc)
        report.checks.append(check)
        if check.status == "pass":
            report.n_passed += 1
        elif check.status == "warn":
            report.n_warned += 1
        else:
            report.n_failed += 1
        pct_errors.append(abs(check.delta_pct))

    report.n_checked = len(report.checks)
    report.median_pct_error = round(statistics.median(pct_errors), 2) if pct_errors else 0.0
    report.worst_pct_error = round(max(pct_errors), 2) if pct_errors else 0.0

    fail_rate = report.n_failed / max(report.n_checked, 1)
    if report.n_failed == 0 and report.median_pct_error <= PASS_PCT:
        report.overall_status = "pass"
    elif fail_rate <= 0.10 and report.median_pct_error <= WARN_PCT:
        report.overall_status = "warn"
    else:
        report.overall_status = "fail"

    if report.overall_status != "pass":
        report.notes.append(
            f"Median dimension error: {report.median_pct_error:.1f}%, "
            f"worst: {report.worst_pct_error:.1f}%. Review the plan before BIM build."
        )

    plan.accuracy_report = report
    logger.info(
        "Accuracy: %s (%d/%d pass, median err %.1f%%, worst %.1f%%)",
        report.overall_status, report.n_passed, report.n_checked,
        report.median_pct_error, report.worst_pct_error,
    )
    return report


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _check_one(dc: DimensionCallout) -> AccuracyCheck:
    measured = math.hypot(
        dc.point_b.x - dc.point_a.x,
        dc.point_b.y - dc.point_a.y,
    )
    claimed = dc.value_in
    delta_in = measured - claimed
    if claimed > 0:
        delta_pct = (delta_in / claimed) * 100.0
    else:
        delta_pct = 100.0

    abs_pct = abs(delta_pct)
    if abs_pct <= PASS_PCT:
        status = "pass"
        notes = ""
    elif abs_pct <= WARN_PCT:
        status = "warn"
        notes = "Within recognisable range but inconsistent."
    else:
        status = "fail"
        notes = "Callout and geometry disagree significantly — likely a hallucinated coordinate."

    return AccuracyCheck(
        callout_text=dc.text,
        claimed_in=round(claimed, 2),
        measured_in=round(measured, 2),
        delta_in=round(delta_in, 2),
        delta_pct=round(delta_pct, 2),
        status=status,
        notes=notes,
    )
