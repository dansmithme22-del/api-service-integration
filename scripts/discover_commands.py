#!/usr/bin/env python3
"""Discover all JSON commands available in the running Archicad instance.

Usage:
    python scripts/discover_commands.py [--port 19723]

Outputs:
    - A list of every command name + signature to stdout.
    - A machine-readable JSON file at output/available_commands.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.connection import ArchicadConnection, DEFAULT_PORT
from src.discovery import discover_commands, discover_types


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Archicad JSON commands.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Archicad JSON port (default {DEFAULT_PORT})")
    args = parser.parse_args()

    print(f"Connecting to Archicad on port {args.port} …")
    try:
        conn = ArchicadConnection(port=args.port).connect()
    except Exception as exc:
        print(f"\n✗ Could not connect: {exc}")
        print("  Make sure Archicad is running and the JSON API is enabled.")
        print(f"  (Edit > Preferences > Experimental > Python / JSON port = {args.port})")
        sys.exit(1)

    # --- Commands ---
    commands = discover_commands(conn)
    print(f"\n{'='*60}")
    print(f" {len(commands)} commands available")
    print(f"{'='*60}\n")
    for c in commands:
        print(f"  {c['name']}{c['sig']}")
        if c["doc"]:
            for line in c["doc"].split("\n"):
                print(f"      {line}")
        print()

    # --- Types ---
    types = discover_types(conn)
    print(f"\n{'='*60}")
    print(f" {len(types)} types available")
    print(f"{'='*60}\n")
    for t in types:
        print(f"  {t}")

    # --- Export ---
    out_dir = Path(__file__).resolve().parents[1] / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "available_commands.json"
    out_path.write_text(json.dumps({
        "commands": commands,
        "types": types,
    }, indent=2))
    print(f"\n✓ Saved to {out_path}")


if __name__ == "__main__":
    main()
