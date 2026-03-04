"""Command discovery — list every JSON command Archicad exposes.

Run standalone:
    python -m src.discovery
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from .connection import ArchicadConnection

logger = logging.getLogger(__name__)


def discover_commands(conn: ArchicadConnection) -> list[dict[str, Any]]:
    """Return a list of dicts describing each available command.

    Each dict has:
        name : str          — command / method name
        doc  : str | None   — docstring (if any)
        sig  : str          — call signature
    """
    commands_obj = conn.commands
    results: list[dict[str, Any]] = []

    for attr_name in sorted(dir(commands_obj)):
        if attr_name.startswith("_"):
            continue
        attr = getattr(commands_obj, attr_name, None)
        if not callable(attr):
            continue
        sig = ""
        try:
            sig = str(inspect.signature(attr))
        except (ValueError, TypeError):
            pass
        results.append({
            "name": attr_name,
            "doc": (inspect.getdoc(attr) or "")[:200],
            "sig": sig,
        })

    logger.info("Discovered %d commands.", len(results))
    return results


def discover_types(conn: ArchicadConnection) -> list[str]:
    """Return names of all type objects exposed by the SDK."""
    types_obj = conn.types
    return sorted(n for n in dir(types_obj) if not n.startswith("_"))


def print_commands(conn: ArchicadConnection) -> None:
    """Pretty-print all available commands to stdout."""
    cmds = discover_commands(conn)
    print(f"\n{'='*60}")
    print(f" Archicad JSON Commands — {len(cmds)} available")
    print(f"{'='*60}\n")
    for c in cmds:
        print(f"  {c['name']}{c['sig']}")
        if c["doc"]:
            print(f"      {c['doc']}")
        print()


# Allow running as module: python -m src.discovery
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ac = ArchicadConnection().connect()
    print_commands(ac)
