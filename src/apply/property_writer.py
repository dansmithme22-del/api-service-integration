"""Property writer — push note text into Archicad custom properties.

Strategy:
1. Ensure a custom User-Defined property group + property exists
   (e.g. "LayoutAnnotation" → "SheetNotesText").
2. For each layout, set that property to the flat-text note content.
3. A GDL "Sheet Notes" object on the Master Layout reads the property via
   ``REQUEST ("LAYOUT_*", ...)`` or ``REQUEST ("Property_Value", ...)``
   and renders it as multi-line text.

This is the **property-driven** approach from the architecture doc.
"""

from __future__ import annotations

import logging
from typing import Any

from ..connection import ArchicadConnection
from ..extract.properties import resolve_property_ids, set_property_values
from ..models.data_model import ACLayout, SheetNotes

logger = logging.getLogger(__name__)

# The custom property we create / write to.
PROPERTY_GROUP = "LayoutAnnotation"
PROPERTY_NAME = "SheetNotesText"
PROPERTY_FULL = f"{PROPERTY_GROUP}_{PROPERTY_NAME}"


def ensure_custom_property(conn: ArchicadConnection) -> Any:
    """Create the custom property if it doesn't already exist.

    Returns the property ID object, or None on failure.

    NOTE: The Python JSON API may not support *creating* property definitions.
    If ``CreatePropertyDefinition`` is not available, the property must be
    created manually in Archicad (Property Manager) or via the C++ API.
    This function will attempt to resolve the property; if it doesn't exist
    it logs a clear instruction.
    """
    ids = resolve_property_ids(conn, [PROPERTY_FULL])
    pid = ids.get(PROPERTY_FULL)

    if pid is not None:
        logger.info("Custom property '%s' already exists.", PROPERTY_FULL)
        return pid

    # Attempt creation via a possible JSON command
    try:
        definition = conn.types.PropertyDefinition(
            group=conn.types.PropertyGroup(PROPERTY_GROUP),
            name=PROPERTY_NAME,
            description="Auto-generated sheet annotation text.",
            valueType=conn.types.PropertyValueType("String"),
            defaultValue=conn.types.NormalStringPropertyValue(""),
            availability=["Layout"],
        )
        conn.commands.CreatePropertyDefinition(definition)
        logger.info("Created custom property '%s'.", PROPERTY_FULL)
        # Re-resolve
        ids = resolve_property_ids(conn, [PROPERTY_FULL])
        return ids.get(PROPERTY_FULL)
    except Exception as exc:
        logger.warning(
            "Could not auto-create property '%s' (%s). "
            "Please create it manually in Property Manager:\n"
            "  Group: %s\n"
            "  Name: %s\n"
            "  Type: String\n"
            "  Available for: Layouts",
            PROPERTY_FULL, exc, PROPERTY_GROUP, PROPERTY_NAME,
        )
        return None


def write_notes_to_layouts(
    conn: ArchicadConnection,
    layouts: list[ACLayout],
    sheet_notes_map: dict[str, SheetNotes],
) -> int:
    """Write the flat-text note content to each layout's custom property.

    ``sheet_notes_map`` is keyed by ``sheet_id``.
    Returns the number of layouts successfully updated.
    """
    pid = ensure_custom_property(conn)
    if pid is None:
        logger.error("Cannot write notes — property not available.")
        return 0

    element_ids = []
    values = []
    for layout in layouts:
        sn = sheet_notes_map.get(layout.sheet_id)
        if sn is None:
            continue
        try:
            eid = conn.types.ElementId(layout.guid)
            element_ids.append(eid)
            values.append(sn.render_flat_text())
        except Exception:
            logger.warning("Could not build ElementId for layout %s", layout.sheet_id)

    if not element_ids:
        logger.warning("No layout elements to update.")
        return 0

    ok = set_property_values(conn, element_ids, pid, values)
    if ok:
        logger.info("Updated %d layouts with notes.", len(element_ids))
        return len(element_ids)
    return 0
