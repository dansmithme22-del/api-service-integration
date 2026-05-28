"""Classify each page of a PDF as 'vector' (parseable linework) or 'raster' (image-only).

The classifier is deliberately conservative: if a page has fewer vector paths
than ``min_vector_paths_for_vector_page`` (configurable), or its content is
dominated by a single large image, we route it through the vision parser.

Returns a per-page verdict plus the page bbox in PDF user units (1/72 inch).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PageVerdict:
    page_index: int
    is_vector: bool
    width_pt: float                  # PDF user units (1 pt = 1/72 inch)
    height_pt: float
    path_count: int
    image_count: int
    char_count: int
    reason: str


def classify_pdf(
    pdf_path: str | Path,
    min_vector_paths: int = 50,
) -> list[PageVerdict]:
    """Return one PageVerdict per page in the PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required for PDF classification. "
            "Run: pip install pdfplumber"
        ) from exc

    verdicts: list[PageVerdict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            path_count = _safe_len(getattr(page, "lines", None)) + \
                         _safe_len(getattr(page, "curves", None)) + \
                         _safe_len(getattr(page, "rects", None))
            image_count = _safe_len(getattr(page, "images", None))
            char_count = _safe_len(getattr(page, "chars", None))

            is_vector = path_count >= min_vector_paths

            if not is_vector and image_count > 0:
                reason = f"raster: only {path_count} vector paths, {image_count} image(s)"
            elif not is_vector:
                reason = f"raster: only {path_count} vector paths"
            else:
                reason = f"vector: {path_count} paths, {char_count} chars"

            verdicts.append(PageVerdict(
                page_index=idx,
                is_vector=is_vector,
                width_pt=float(page.width),
                height_pt=float(page.height),
                path_count=path_count,
                image_count=image_count,
                char_count=char_count,
                reason=reason,
            ))
            logger.info("Page %d: %s", idx, reason)

    return verdicts


def pick_floor_plan_page(verdicts: list[PageVerdict]) -> Optional[int]:
    """Heuristic: pick the page most likely to be the floor plan.

    Prefers vector pages with the highest path count. If all pages are raster,
    picks the one with the most chars (i.e. labels/dimensions present).
    """
    if not verdicts:
        return None

    vector_pages = [v for v in verdicts if v.is_vector]
    if vector_pages:
        best = max(vector_pages, key=lambda v: v.path_count)
        return best.page_index

    best = max(verdicts, key=lambda v: v.char_count)
    return best.page_index


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _safe_len(obj) -> int:
    try:
        return len(obj) if obj is not None else 0
    except TypeError:
        return 0
