"""JSON exporter — write the SheetNotes artefact to disk.

This is the safest "apply" strategy: nothing in Archicad is mutated.
The output file can be version-controlled, reviewed, and consumed by
downstream tools (GDL objects, InDesign scripts, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..models.data_model import ProjectNotesOutput

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def export_json(
    notes: ProjectNotesOutput,
    output_path: Path | str | None = None,
) -> Path:
    """Serialise the ``ProjectNotesOutput`` to ``SheetNotes.json``.

    Returns the path to the written file.
    """
    if output_path is None:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = _OUTPUT_DIR / "SheetNotes.json"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = notes.model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info("Exported SheetNotes.json → %s", output_path)
    return output_path


def export_per_sheet_files(
    notes: ProjectNotesOutput,
    output_dir: Path | str | None = None,
) -> list[Path]:
    """Write one ``<sheet_id>.json`` file per layout.

    Useful when each GDL object needs to read only its own sheet's data.
    """
    if output_dir is None:
        output_dir = _OUTPUT_DIR / "per_sheet"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for sheet in notes.sheets:
        p = output_dir / f"{sheet.sheet_id}.json"
        p.write_text(json.dumps(sheet.model_dump(mode="json"), indent=2, default=str))
        paths.append(p)

    logger.info("Exported %d per-sheet files to %s", len(paths), output_dir)
    return paths


def export_flat_text(
    notes: ProjectNotesOutput,
    output_dir: Path | str | None = None,
) -> list[Path]:
    """Write one ``<sheet_id>.txt`` file per layout with flattened note text.

    These plain-text files can be consumed by the property-writer or pasted
    manually.
    """
    if output_dir is None:
        output_dir = _OUTPUT_DIR / "flat_text"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for sheet in notes.sheets:
        p = output_dir / f"{sheet.sheet_id}.txt"
        p.write_text(sheet.render_flat_text())
        paths.append(p)

    logger.info("Exported %d flat-text files to %s", len(paths), output_dir)
    return paths
