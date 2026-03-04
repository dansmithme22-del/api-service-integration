"""Archicad connection wrapper.

Encapsulates the ``archicad`` PyPI package's ``ACConnection`` so the rest of
the codebase never imports the SDK directly.  This makes it easy to:

* swap to a mock for testing,
* handle connection errors in one place,
* pin the port / retry logic globally.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default port Archicad 29 listens on for JSON commands.
DEFAULT_PORT = 19723


class ArchicadConnection:
    """Thin wrapper around ``archicad.ACConnection``."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self._conn: Any = None  # archicad.ACConnection instance
        self._commands: Any = None
        self._types: Any = None
        self._utilities: Any = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> "ArchicadConnection":
        """Establish a live connection to the running Archicad instance.

        Raises ``ConnectionError`` if Archicad is not reachable.
        """
        try:
            from archicad import ACConnection  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'archicad' package is not installed.  "
                "Run:  pip install archicad"
            ) from exc

        logger.info("Connecting to Archicad on port %d …", self.port)
        self._conn = ACConnection.connect(self.port)
        self._commands = self._conn.commands
        self._types = self._conn.types
        self._utilities = self._conn.utilities
        logger.info("Connected successfully.")
        return self

    @property
    def connected(self) -> bool:
        return self._conn is not None

    # ------------------------------------------------------------------
    # Accessors (typed for IDE help)
    # ------------------------------------------------------------------

    @property
    def commands(self) -> Any:
        """The ``archicad`` commands namespace."""
        self._ensure()
        return self._commands

    @property
    def types(self) -> Any:
        """The ``archicad`` types namespace."""
        self._ensure()
        return self._types

    @property
    def utilities(self) -> Any:
        """The ``archicad`` utilities namespace."""
        self._ensure()
        return self._utilities

    # ------------------------------------------------------------------
    # Raw command execution (for commands not wrapped by the SDK)
    # ------------------------------------------------------------------

    def execute_raw(self, command_name: str, parameters: Optional[dict] = None) -> Any:
        """Execute an arbitrary JSON command by name.

        This is useful for commands the Python SDK doesn't expose helpers for,
        or commands added by the Additional JSON Commands Add-On.
        """
        self._ensure()
        # The SDK exposes a generic runner on the connection object.
        # Depending on the archicad package version the API may differ:
        try:
            # archicad >= 28.x style
            return self._conn.request(command_name, parameters or {})
        except AttributeError:
            # Older style — fall back to the low-level post
            import json, urllib.request
            url = f"http://127.0.0.1:{self.port}"
            payload = json.dumps({
                "command": command_name,
                "parameters": parameters or {},
            }).encode()
            req = urllib.request.Request(url, data=payload,
                                        headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure(self) -> None:
        if not self.connected:
            raise RuntimeError(
                "Not connected to Archicad.  Call .connect() first."
            )
