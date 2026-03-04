"""Renovation-status extraction and mapping.

Archicad stores renovation status as an integer (or enum string depending on
the API path):

    1 → Existing
    2 → Demolition
    3 → New Construction

This module normalises any representation to our ``Phase`` enum and provides
helpers that classify elements per-layout into phase buckets.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models.data_model import ACElement, Phase

logger = logging.getLogger(__name__)

# Load phase config for ac_status → Phase mapping
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "phases.json"
_STATUS_MAP: dict[int, Phase] = {}

try:
    _phase_data = json.loads(_CONFIG_PATH.read_text())
    for p in _phase_data.get("phases", []):
        _STATUS_MAP[p["ac_status"]] = Phase(p["label"])
except Exception:
    # Fallback hard-coded map
    _STATUS_MAP = {1: Phase.EXISTING, 2: Phase.DEMOLITION, 3: Phase.NEW_CONSTRUCTION}


# String variants Archicad may return
_STRING_MAP: dict[str, Phase] = {
    "existing": Phase.EXISTING,
    "new": Phase.NEW_CONSTRUCTION,
    "new construction": Phase.NEW_CONSTRUCTION,
    "demolition": Phase.DEMOLITION,
    "demolished": Phase.DEMOLITION,
}


def map_renovation_value(raw: Any) -> Phase | None:
    """Convert a raw property value (int, str, enum) to a ``Phase`` enum.

    Returns ``None`` if the value cannot be mapped.
    """
    if raw is None or raw == "":
        return None

    # Integer path
    if isinstance(raw, (int, float)):
        return _STATUS_MAP.get(int(raw))

    # String path
    s = str(raw).strip().lower()
    if s in _STRING_MAP:
        return _STRING_MAP[s]

    # Try matching enum member names (e.g. "New Construction")
    for phase in Phase:
        if phase.value.lower() == s:
            return phase

    logger.warning("Unmappable renovation value: %r", raw)
    return None


def classify_elements_by_phase(
    elements: list[ACElement],
) -> dict[Phase, list[ACElement]]:
    """Bucket elements into phase groups.

    Elements with ``renovation_status=None`` are placed under a special key
    whose string value is an empty string (we skip them in rules).
    """
    buckets: dict[Phase, list[ACElement]] = {p: [] for p in Phase}
    for elem in elements:
        if elem.renovation_status is not None:
            buckets[elem.renovation_status].append(elem)
    return buckets


def phase_summary(elements: list[ACElement]) -> dict[str, int]:
    """Return a quick count of elements per phase."""
    buckets = classify_elements_by_phase(elements)
    return {phase.value: len(elems) for phase, elems in buckets.items()}
