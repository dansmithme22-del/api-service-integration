"""Property helpers — resolve, read, and write Archicad element properties."""

from __future__ import annotations

import logging
from typing import Any

from ..connection import ArchicadConnection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def get_all_property_names(conn: ArchicadConnection) -> list[dict[str, str]]:
    """Return every property group + name pair available in the project.

    Each dict has keys: ``group``, ``name``, ``id`` (stringified).
    """
    results: list[dict[str, str]] = []
    try:
        props = conn.commands.GetAllPropertyNames()
        for p in props:
            results.append({
                "group": getattr(p, "group", ""),
                "name": getattr(p, "name", ""),
                "id": str(getattr(p, "propertyId", "")),
            })
    except Exception as exc:
        logger.error("GetAllPropertyNames failed: %s", exc)
    logger.info("Discovered %d properties.", len(results))
    return results


# ---------------------------------------------------------------------------
# Resolution — property name → property ID object
# ---------------------------------------------------------------------------

def resolve_property_ids(
    conn: ArchicadConnection,
    property_names: list[str],
) -> dict[str, Any]:
    """Given human-readable property names (e.g. ``'General_RenovationStatus'``),
    return a mapping of name → SDK property-ID object.

    The SDK expects property names as a list of
    ``types.PropertyUserId(group, name)`` where group and name are separated by
    ``_`` (or by the group/name pair from ``GetAllPropertyNames``).
    """
    id_map: dict[str, Any] = {}
    try:
        user_ids = []
        for pname in property_names:
            # Convention: "Group_PropertyName" → group="General", name="ElementLayer"
            parts = pname.split("_", 1)
            if len(parts) == 2:
                user_ids.append(
                    conn.types.PropertyUserId(parts[0], parts[1])
                )
            else:
                user_ids.append(
                    conn.types.PropertyUserId("General", parts[0])
                )

        resolved = conn.commands.GetPropertyIds(user_ids)
        for pname, pid in zip(property_names, resolved):
            if pid is not None:
                id_map[pname] = pid
                logger.debug("Resolved %s → %s", pname, pid)
            else:
                logger.warning("Could not resolve property: %s", pname)
    except Exception as exc:
        logger.error("resolve_property_ids failed: %s", exc)

    return id_map


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def get_property_values(
    conn: ArchicadConnection,
    element_ids: list[Any],
    property_ids: list[Any],
) -> list[dict[str, Any]]:
    """Read property values for a batch of elements.

    Returns a list (one per element) of dicts mapping property-name → value.
    """
    if not element_ids or not property_ids:
        return [{} for _ in element_ids]

    try:
        raw = conn.commands.GetPropertyValuesOfElements(element_ids, property_ids)
        # raw is a 2D matrix: raw[elem_idx][prop_idx]
        results: list[dict[str, Any]] = []
        for row in raw:
            row_dict: dict[str, Any] = {}
            for pid, cell in zip(property_ids, row):
                key = str(pid)
                val = _extract_cell_value(cell)
                row_dict[key] = val
            results.append(row_dict)
        return results
    except Exception as exc:
        logger.error("GetPropertyValuesOfElements failed: %s", exc)
        return [{} for _ in element_ids]


# ---------------------------------------------------------------------------
# Writing (Apply layer calls this)
# ---------------------------------------------------------------------------

def set_property_values(
    conn: ArchicadConnection,
    element_ids: list[Any],
    property_id: Any,
    values: list[str],
) -> bool:
    """Set a single property to a list of string values on matching elements.

    ``values[i]`` is written to ``element_ids[i]``.
    Returns True on success.
    """
    try:
        value_wraps = []
        for eid, val in zip(element_ids, values):
            value_wraps.append(
                conn.types.ElementPropertyValue(
                    eid, property_id,
                    conn.types.NormalSingleEnumPropertyValue(val)
                    if isinstance(val, str)
                    else conn.types.NormalNumberPropertyValue(val)
                )
            )
        conn.commands.SetPropertyValuesOfElements(value_wraps)
        logger.info("Set property on %d elements.", len(element_ids))
        return True
    except Exception as exc:
        logger.error("SetPropertyValuesOfElements failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_cell_value(cell: Any) -> Any:
    """Pull a plain Python value out of an SDK property-value cell."""
    # The SDK wraps values in types like NormalSingleEnumPropertyValue, etc.
    try:
        pv = cell.propertyValue
        val = getattr(pv, "value", pv)
        # Unwrap enum display strings
        if hasattr(val, "displayValue"):
            return val.displayValue
        if hasattr(val, "nonLocalizedValue"):
            return val.nonLocalizedValue
        return val
    except AttributeError:
        return None
