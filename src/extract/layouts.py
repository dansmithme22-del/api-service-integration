"""Extract layouts and placed drawings from the Archicad navigator tree."""

from __future__ import annotations

import logging
from typing import Any

from ..connection import ArchicadConnection
from ..models.data_model import ACLayout, ACDrawing, parse_sheet_id

logger = logging.getLogger(__name__)


def get_navigator_tree(conn: ArchicadConnection) -> Any:
    """Return the full navigator item tree (raw SDK object).

    The tree is a nested structure: project → folders → views / layouts.
    """
    try:
        tree = conn.commands.GetNavigatorItemTree(
            conn.types.NavigatorTreeId("LayoutBook")
        )
        logger.info("Retrieved LayoutBook navigator tree.")
        return tree
    except Exception as exc:
        logger.warning("GetNavigatorItemTree('LayoutBook') failed: %s", exc)
        # Fallback: try the generic call without specifying tree type
        try:
            tree = conn.commands.GetNavigatorItemTree()
            logger.info("Retrieved generic navigator tree.")
            return tree
        except Exception as exc2:
            logger.error("Could not retrieve navigator tree: %s", exc2)
            return None


def _walk_tree(node: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Recursively walk the navigator tree and extract flat item dicts."""
    items: list[dict[str, Any]] = []
    try:
        nav_item = node.navigatorItem
        items.append({
            "guid": str(getattr(nav_item, "navigatorItemId", {})
                        if not hasattr(nav_item, "navigatorItemId")
                        else nav_item.navigatorItemId.guid),
            "name": getattr(nav_item, "name", ""),
            "type": getattr(nav_item, "type", ""),
            "depth": depth,
        })
    except AttributeError:
        pass

    children = getattr(node, "children", []) or []
    for child in children:
        items.extend(_walk_tree(child, depth + 1))
    return items


def get_layouts(conn: ArchicadConnection) -> list[ACLayout]:
    """Return a list of ``ACLayout`` models from the Layout Book."""
    tree = get_navigator_tree(conn)
    if tree is None:
        return []

    flat_items = _walk_tree(tree.rootItem if hasattr(tree, "rootItem") else tree)
    logger.info("Navigator tree has %d total items.", len(flat_items))

    layouts: list[ACLayout] = []
    for item in flat_items:
        # Layouts in the tree typically have type "Layout"
        item_type = str(item.get("type", "")).lower()
        if "layout" not in item_type and item.get("depth", 0) < 2:
            continue  # probably a folder

        raw_name = item.get("name", "")
        sheet_id, discipline = parse_sheet_id(raw_name)

        layouts.append(ACLayout(
            guid=item.get("guid", ""),
            layout_name=raw_name,
            sheet_id=sheet_id,
            discipline=discipline,
        ))

    logger.info("Found %d layouts.", len(layouts))
    return layouts


def get_drawings_on_layout(conn: ArchicadConnection, layout_guid: str) -> list[ACDrawing]:
    """Return the Drawing elements placed on a specific Layout.

    This uses ``GetElementsByType`` filtered to drawings, then checks each
    drawing's parent layout GUID.  If the SDK provides a more direct route,
    we prefer that.
    """
    drawings: list[ACDrawing] = []
    try:
        # Try getting drawings directly
        all_drawings = conn.commands.GetElementsByType("Drawing")
        for d in all_drawings:
            # Check if this drawing belongs to the target layout
            # The exact attribute depends on the SDK version
            parent = getattr(d, "parentId", None) or getattr(d, "layoutId", None)
            dguid = str(d.elementId.guid) if hasattr(d, "elementId") else ""
            if parent and str(parent) == layout_guid:
                drawings.append(ACDrawing(
                    guid=dguid,
                    name=getattr(d, "name", ""),
                ))
    except Exception as exc:
        logger.debug("Could not fetch drawings for layout %s: %s", layout_guid, exc)

    return drawings
