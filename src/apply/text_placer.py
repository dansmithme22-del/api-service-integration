"""Text placer — direct 2D text element placement on layouts.

STATUS: STUB.  The Archicad Python/JSON API (as of AC 29) does **not** expose
a command to create or modify 2D text elements on layouts.  This module exists
as the integration point for:

  A) A future JSON command (if Graphisoft adds one), or
  B) The C++ Add-On (see ``addons/layout_annotator_cpp/``).

If you install the "Additional JSON/Python Commands" Add-On, run
``scripts/discover_commands.py`` to check whether a ``CreateTextElement`` or
``CreateLabel`` command becomes available, then implement it here.

For now, use the property-driven approach (``property_writer.py``) or the JSON
export approach (``json_exporter.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from ..connection import ArchicadConnection

logger = logging.getLogger(__name__)


def place_text_on_layout(
    conn: ArchicadConnection,
    layout_guid: str,
    text: str,
    x: float = 10.0,
    y: float = 10.0,
    font_size: float = 2.5,
) -> bool:
    """Place a 2D multi-line text element on a layout.

    Returns True on success, False if the command is unavailable.

    This attempts to use ``CreateTextElement`` if it exists.  If not, it tries
    ``ExecuteAddOnCommand`` targeting the C++ add-on.
    """
    # --- Attempt 1: native JSON command ---
    try:
        result = conn.execute_raw("CreateTextElement", {
            "layoutId": layout_guid,
            "content": text,
            "position": {"x": x, "y": y},
            "fontSize": font_size,
        })
        if result and result.get("succeeded", False):
            logger.info("Placed text on layout %s via CreateTextElement.", layout_guid)
            return True
    except Exception as exc:
        logger.debug("CreateTextElement not available: %s", exc)

    # --- Attempt 2: C++ Add-On bridge ---
    try:
        result = conn.execute_raw("ExecuteAddOnCommand", {
            "addOnCommandId": {
                "commandNamespace": "LayoutAnnotator",
                "commandName": "PlaceText",
            },
            "addOnCommandParameters": {
                "layoutGuid": layout_guid,
                "text": text,
                "x": x,
                "y": y,
                "fontSize": font_size,
            },
        })
        if result:
            logger.info("Placed text on layout %s via C++ Add-On.", layout_guid)
            return True
    except Exception as exc:
        logger.debug("C++ Add-On PlaceText not available: %s", exc)

    logger.warning(
        "Cannot place text on layout %s — no available method. "
        "Use property_writer or json_exporter instead.",
        layout_guid,
    )
    return False
