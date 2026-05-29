"""Extract elements from Archicad.

Reads all (or filtered) elements and returns a list of ``ACElement`` models.
"""

from __future__ import annotations

import logging
from typing import Any

from ..connection import ArchicadConnection
from ..models.data_model import ACElement

logger = logging.getLogger(__name__)

# Archicad element type enum strings the SDK uses.
# We build this dynamically where possible; these are fallbacks.
_ELEMENT_TYPES = [
    "Wall", "Column", "Beam", "Slab", "Roof", "Shell", "Morph",
    "Door", "Window", "Stair", "Railing", "Object", "Lamp", "Zone",
    "Mesh", "CurtainWall", "Skylight",
]


def get_all_elements(conn: ArchicadConnection) -> list[dict[str, Any]]:
    """Return raw element dicts from Archicad (GUID + type)."""
    cmd = conn.commands
    elements: list[dict[str, Any]] = []

    for etype in _ELEMENT_TYPES:
        try:
            type_obj = getattr(conn.types, etype, None)
            if type_obj is None:
                continue
            cmd.GetAllElements()  # returns all element IDs
        except Exception:
            # Some SDK versions require specifying element type differently.
            pass

    # Preferred: use the bulk getter if the SDK version supports it.
    try:
        all_elems = cmd.GetAllElements()
        for e in all_elems:
            elements.append({
                "guid": str(e.elementId.guid),
                "element_type": getattr(e, "type", "Unknown"),
            })
        logger.info("GetAllElements returned %d elements.", len(elements))
        return elements
    except Exception as exc:
        logger.warning("GetAllElements failed (%s). Trying per-type fallback.", exc)

    # Fallback: iterate known types
    for etype in _ELEMENT_TYPES:
        try:
            elems = cmd.GetElementsByType(etype)
            for e in elems:
                elements.append({
                    "guid": str(e.elementId.guid),
                    "element_type": etype,
                })
        except Exception:
            continue

    logger.info("Collected %d elements via per-type fallback.", len(elements))
    return elements


def enrich_elements(
    conn: ArchicadConnection,
    raw_elements: list[dict[str, Any]],
    property_ids: dict[str, Any] | None = None,
) -> list[ACElement]:
    """Attach layer, story, renovation status, and properties to raw elements.

    ``property_ids`` — optional pre-resolved map of property name → property ID
    object.  If not provided, the function resolves Renovation Status automatically
    via ``properties.resolve_property_ids``.
    """
    from .properties import resolve_property_ids, get_property_values
    from .renovation import map_renovation_value

    if not raw_elements:
        return []

    # Build element ID list the SDK uses
    try:
        ElementId = conn.types.ElementId
        element_id_objs = [ElementId(e["guid"]) for e in raw_elements]
    except Exception:
        logger.warning("Could not build ElementId objects; returning basic models.")
        return [
            ACElement(guid=e["guid"], element_type=e.get("element_type", "Unknown"))
            for e in raw_elements
        ]

    # --- Resolve standard properties ---
    wanted_properties = [
        "General_ElementLayer",           # layer name
        "General_FloorNumber",            # story index
        "General_RenovationStatus",       # 1/2/3
    ]
    if property_ids is None:
        property_ids = resolve_property_ids(conn, wanted_properties)

    prop_id_list = [v for v in property_ids.values() if v is not None]
    values_matrix = get_property_values(conn, element_id_objs, prop_id_list)

    # --- Build ACElement models ---
    results: list[ACElement] = []
    for idx, raw in enumerate(raw_elements):
        props_row = values_matrix[idx] if idx < len(values_matrix) else {}
        layer = _extract_str(props_row, "General_ElementLayer")
        story = _extract_str(props_row, "General_FloorNumber")
        renov_raw = _extract_str(props_row, "General_RenovationStatus")
        phase = map_renovation_value(renov_raw)

        results.append(ACElement(
            guid=raw["guid"],
            element_type=raw.get("element_type", "Unknown"),
            layer_name=layer,
            story_name=story,
            renovation_status=phase,
            properties=props_row,
        ))

    logger.info("Enriched %d elements.", len(results))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_str(prop_row: dict, key_fragment: str) -> str:
    """Pull a string value from a property-values dict, matching by key fragment."""
    for k, v in prop_row.items():
        if key_fragment.lower() in str(k).lower():
            return str(v) if v is not None else ""
    return ""
