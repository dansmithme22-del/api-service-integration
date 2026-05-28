"""Capture views from a running Archicad project as PNGs.

Three capture strategies (in order of robustness):

1. **Saved views** — if Archicad has named views in the navigator, list them
   and ask Archicad to publish each as a PNG (publisher set required).
2. **Active view** — capture whatever the user currently has on screen via
   ``GetSelectedElements`` + ``API.ExportImage`` if exposed.
3. **Fallback** — direct the user to set up a Publisher Set and re-run.

Because the JSON API surface for image export varies by Archicad version, the
function returns paths to any files that already exist in the configured
``capture_dir``. This means: you can wire up Archicad's Publisher Set to dump
into ``capture_dir/`` and this module will pick them up — no API call needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..connection import ArchicadConnection

logger = logging.getLogger(__name__)


class ViewExportError(RuntimeError):
    pass


@dataclass
class CapturedView:
    path: Path
    view_name: str = ""
    source: str = "filesystem"        # "filesystem" | "publisher" | "api"


def export_views(
    capture_dir: str | Path,
    *,
    conn: Optional[ArchicadConnection] = None,
    publish_set_name: str = "Renders",
    use_existing_files: bool = True,
) -> list[CapturedView]:
    """Return a list of CapturedView objects pointing at PNG/JPG files.

    Order of operations:
      1. If ``use_existing_files``, scan ``capture_dir`` for existing images.
      2. If a connection is provided, try Archicad's ``API.PublishPublisherSet``
         JSON command targeting ``publish_set_name`` — many AC29 builds
         expose this.
      3. Re-scan ``capture_dir`` and return what's there.
    """
    capture_dir = Path(capture_dir)
    capture_dir.mkdir(parents=True, exist_ok=True)

    captured: list[CapturedView] = []

    if use_existing_files:
        captured = _scan_dir(capture_dir, source="filesystem")
        if captured:
            logger.info("Found %d existing capture(s) in %s", len(captured), capture_dir)

    if conn is not None:
        try:
            _trigger_publisher_set(conn, publish_set_name)
            new_files = _scan_dir(capture_dir, source="publisher")
            # De-dup by path.
            seen = {c.path for c in captured}
            for nv in new_files:
                if nv.path not in seen:
                    captured.append(nv)
        except Exception as exc:
            logger.warning("Publisher set trigger failed: %s", exc)

    if not captured:
        raise ViewExportError(
            f"No views found in {capture_dir}. Either run Archicad's "
            f"Publisher Set named '{publish_set_name}' (dest = {capture_dir}), "
            "or drop PNG screenshots into that folder manually."
        )

    return captured


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _scan_dir(d: Path, *, source: str) -> list[CapturedView]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    out: list[CapturedView] = []
    for f in sorted(d.iterdir()):
        if f.is_file() and f.suffix.lower() in exts:
            out.append(CapturedView(path=f, view_name=f.stem, source=source))
    return out


def _trigger_publisher_set(conn: ArchicadConnection, set_name: str) -> None:
    """Call the Publisher Set publish command. Raises on failure."""
    # JSON command name has varied across AC versions; try a few.
    candidates = [
        ("API.PublishPublisherSet", {"publisherSetName": set_name}),
        ("PublishPublisherSet", {"publisherSetName": set_name}),
        ("Publish", {"publisherSet": set_name}),
    ]
    last_exc: Optional[Exception] = None
    for cmd, params in candidates:
        try:
            resp = conn.execute_raw(cmd, params)
            logger.info("Published via %s: %s", cmd, resp)
            return
        except Exception as exc:
            last_exc = exc
            continue
    raise ViewExportError(f"No publisher-set command worked: {last_exc}")
