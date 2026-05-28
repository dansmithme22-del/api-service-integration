#!/usr/bin/env python3
"""Render Archicad view PNGs through Gemini 2.5 Flash Image.

Usage:
    # Render every PNG in capture_dir/ -> render_output/
    python scripts/render_views.py --capture-dir captures/

    # Custom style:
    python scripts/render_views.py --capture-dir captures/ \\
        --style "minimal scandinavian veterinary clinic, white walls, oak floors"

    # Pull captures from Archicad first via Publisher Set 'Renders':
    python scripts/render_views.py --from-archicad --port 19723 \\
        --capture-dir captures/

Output:
    render_output/<view_name>_render.png  for each capture
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from src.render import export_views, render_batch
from src.render.gemini_render import RenderJob, DEFAULT_STYLE_PROMPT
from src.ingest.runner import load_config
from src.connection import ArchicadConnection, DEFAULT_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("render_views")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Archicad views via Gemini 2.5 Flash Image.")
    parser.add_argument("--capture-dir", type=Path, required=True,
                        help="Directory containing source PNG/JPG screenshots.")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Directory for rendered output (default: ./render_output)")
    parser.add_argument("--style", type=str, default=DEFAULT_STYLE_PROMPT,
                        help="Override the style prompt.")
    parser.add_argument("--from-archicad", action="store_true",
                        help="Also trigger Archicad's Publisher Set first.")
    parser.add_argument("--publisher-set", type=str, default="Renders")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--concurrent", type=int, default=3,
                        help="Max parallel render jobs (default 3).")
    args = parser.parse_args()

    cfg = load_config()
    out_dir = args.out_dir or (REPO_ROOT / cfg.get("output", {}).get("render_dir", "render_output"))
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = None
    if args.from_archicad:
        try:
            conn = ArchicadConnection(port=args.port).connect()
        except Exception as exc:
            logger.error("Could not connect to Archicad on port %d: %s", args.port, exc)
            sys.exit(1)

    captures = export_views(
        args.capture_dir,
        conn=conn,
        publish_set_name=args.publisher_set,
    )
    logger.info("Found %d captures to render.", len(captures))

    jobs = [
        RenderJob(
            src=c.path,
            dst=out_dir / f"{c.path.stem}_render.png",
            style_prompt=args.style,
        )
        for c in captures
    ]

    rendered = render_batch(
        jobs,
        max_concurrent=args.concurrent,
        model=cfg.get("render", {}).get("image_model", "gemini-2.5-flash-image"),
    )

    print(f"\n✓ Rendered {len(rendered)}/{len(jobs)} views. Output: {out_dir}\n")


if __name__ == "__main__":
    main()
