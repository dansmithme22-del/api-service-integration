"""Phase analyzer — determines which phases are present per layout.

Takes the extracted model data, groups elements by layout, and summarises which
renovation phases are represented (and with which element types).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from ..models.data_model import ACElement, ACLayout, Phase

logger = logging.getLogger(__name__)


class LayoutPhaseReport:
    """Summary of phase presence for a single layout."""

    def __init__(self, layout: ACLayout):
        self.layout = layout
        # phase → list of element types present
        self.phase_element_types: dict[Phase, set[str]] = defaultdict(set)
        # phase → total count
        self.phase_counts: dict[Phase, int] = defaultdict(int)
        # element_type → count (regardless of phase)
        self.element_type_counts: dict[str, int] = defaultdict(int)
        # classification → count
        self.classification_counts: dict[str, int] = defaultdict(int)

    def has_phase(self, phase: Phase) -> bool:
        return self.phase_counts.get(phase, 0) > 0

    def has_element_type_in_phase(self, phase: Phase, element_type: str) -> bool:
        return element_type in self.phase_element_types.get(phase, set())

    def has_classification(self, classification: str) -> bool:
        for cls_key, cnt in self.classification_counts.items():
            if classification.lower() in cls_key.lower() and cnt > 0:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_id": self.layout.sheet_id,
            "phase_counts": {p.value: c for p, c in self.phase_counts.items()},
            "phase_element_types": {
                p.value: sorted(types) for p, types in self.phase_element_types.items()
            },
            "element_type_counts": dict(self.element_type_counts),
            "classification_counts": dict(self.classification_counts),
        }


def analyse_layout(
    layout: ACLayout,
    elements: list[ACElement],
) -> LayoutPhaseReport:
    """Build a ``LayoutPhaseReport`` for a single layout.

    ``elements`` should already be filtered to only those elements visible
    on this layout/view.  If we cannot yet filter (API limitation), pass all
    elements and the rules engine will still produce correct results for the
    phases that *exist in the project*.
    """
    report = LayoutPhaseReport(layout)

    for elem in elements:
        report.element_type_counts[elem.element_type] += 1

        if elem.classification:
            report.classification_counts[elem.classification] += 1

        if elem.renovation_status is not None:
            report.phase_counts[elem.renovation_status] += 1
            report.phase_element_types[elem.renovation_status].add(elem.element_type)

    return report


def analyse_all_layouts(
    layouts: list[ACLayout],
    all_elements: list[ACElement],
    layout_element_map: dict[str, list[ACElement]] | None = None,
) -> dict[str, LayoutPhaseReport]:
    """Analyse every layout.

    ``layout_element_map`` maps layout GUID → elements visible on that layout.
    If not provided, *all* elements are attributed to *every* layout (conservative
    approach when we can't filter).  This means every applicable rule fires on
    every sheet — you can tighten this once per-layout element lists are available.
    """
    reports: dict[str, LayoutPhaseReport] = {}

    for layout in layouts:
        elems = (
            layout_element_map.get(layout.guid, all_elements)
            if layout_element_map
            else all_elements
        )
        reports[layout.guid] = analyse_layout(layout, elems)

    logger.info("Analysed %d layouts.", len(reports))
    return reports
