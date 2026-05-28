"""Top-level orchestrator: PDF path in, PlanGraph out.

Routes each page through the vector parser or the vision parser based on
:func:`pdf_classifier.classify_pdf`, then normalizes geometry into a PlanGraph.

For multi-page PDFs we currently return *one* PlanGraph for the page that
``pdf_classifier.pick_floor_plan_page`` chooses (the page with the most
linework, or the most text if all pages are raster).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .accuracy_checker import check_plan_accuracy
from .hybrid import hybrid_ingest
from .pdf_classifier import classify_pdf, pick_floor_plan_page
from .plan_model import PlanGraph
from .geometry_normalizer import build_plan_graph
from .vector_parser import parse_vector_page
from .vector_hybrid import vector_hybrid_ingest
from .vector_truth import vector_truth_ingest
from .vision_parser import VisionConfig, parse_raster_page

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "ingest.json"


def load_config(config_path: Optional[Path] = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    if not path.exists():
        logger.warning("Config not found at %s; using empty config.", path)
        return {}
    with open(path) as f:
        return json.load(f)


def ingest_pdf(
    pdf_path: str | Path,
    *,
    project_name: str = "",
    level_name: str = "Level 1",
    page_index: Optional[int] = None,
    force: Optional[str] = None,         # "vector" | "vision" | None
    config_path: Optional[Path] = None,
    scale_override_in_per_pt: Optional[float] = None,
    min_line_width_pt_override: Optional[float] = None,
    reference_pdf: Optional[str | Path] = None,
    reference_page_index: int = 0,
    anchor_bbox_override: Optional[list[float]] = None,
    refine_anchor: bool = True,
    vision_provider: Optional[str] = None,
) -> PlanGraph:
    """Ingest a PDF and return a PlanGraph for one page.

    Parameters
    ----------
    pdf_path
        Path to the input PDF.
    project_name
        Stored on the resulting PlanGraph.
    level_name
        Level label (e.g. "Level 1", "Ground Floor").
    page_index
        Override the auto-selected floor-plan page.
    force
        Override the classifier: ``"vector"`` or ``"vision"``.
    config_path
        Override the default ``config/ingest.json``.
    """
    cfg = load_config(config_path)
    classifier_cfg = cfg.get("classifier", {})
    parser_cfg = cfg.get("vector_parser", {})
    vision_cfg_dict = cfg.get("vision_parser", {})

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    verdicts = classify_pdf(
        pdf_path,
        min_vector_paths=classifier_cfg.get("min_vector_paths_for_vector_page", 50),
    )
    if page_index is None:
        chosen = pick_floor_plan_page(verdicts)
        if chosen is None:
            raise RuntimeError(f"No pages found in {pdf_path}")
        page_index = chosen

    verdict = verdicts[page_index]
    route = force or ("vector" if verdict.is_vector else "vision")
    logger.info(
        "Routing page %d (%s) via %s parser.",
        page_index, verdict.reason, route,
    )

    if route == "vector-hybrid":
        plan = vector_hybrid_ingest(
            pdf_path,
            page_index,
            project_name=project_name,
            level_name=level_name,
            vision_config=VisionConfig(
                model=vision_cfg_dict.get("model", ""),
                fallback_model=vision_cfg_dict.get("fallback_model", ""),
                image_dpi=int(vision_cfg_dict.get("image_dpi", 200)),
                max_pages=int(vision_cfg_dict.get("max_pages_per_pdf", 20)),
                provider=vision_provider or vision_cfg_dict.get("provider", ""),
            ),
            min_wall_length_norm=parser_cfg.get("min_wall_length_norm", 0.015),
            pair_max_sep_norm=parser_cfg.get("wall_pair_max_separation_norm", 0.006),
            min_line_width_pt=parser_cfg.get("min_line_width_pt", 0.36),
        )
        return plan

    if route == "vector-truth":
        plan = vector_truth_ingest(
            pdf_path,
            page_index,
            project_name=project_name,
            level_name=level_name,
            min_wall_length_norm=parser_cfg.get("min_wall_length_norm", 0.012),
            pair_max_sep_norm=parser_cfg.get("wall_pair_max_separation_norm", 0.015),
            min_line_width_pt=parser_cfg.get("min_line_width_pt", 0.36),
        )
        return plan

    if route == "hybrid":
        plan = hybrid_ingest(
            pdf_path,
            page_index,
            project_name=project_name,
            level_name=level_name,
            vision_config=VisionConfig(
                model=vision_cfg_dict.get("model", ""),
                fallback_model=vision_cfg_dict.get("fallback_model", ""),
                image_dpi=int(vision_cfg_dict.get("image_dpi", 200)),
                max_pages=int(vision_cfg_dict.get("max_pages_per_pdf", 20)),
                provider=vision_provider or vision_cfg_dict.get("provider", ""),
            ),
            min_line_width_pt=parser_cfg.get("min_line_width_pt", 0.36),
        )
        if anchor_bbox_override is not None and len(anchor_bbox_override) == 4 and plan.page:
            plan.page.drawing_area_norm_bbox = [
                max(0.0, min(1.0, float(v))) for v in anchor_bbox_override
            ]
        return plan

    if route == "vector":
        geom = parse_vector_page(pdf_path, page_index)
        min_lw = min_line_width_pt_override
        if min_lw is None:
            min_lw = parser_cfg.get("min_line_width_pt", 0.0)
        plan = build_plan_graph(
            geom,
            pdf_path=str(pdf_path),
            project_name=project_name,
            level_name=level_name,
            min_wall_length_in=parser_cfg.get("min_wall_length_in", 6.0),
            max_wall_thickness_in=parser_cfg.get("max_wall_thickness_in", 12.0),
            pair_max_separation_in=parser_cfg.get("wall_pair_max_separation_in", 14.0),
            min_line_width_pt=min_lw,
            scale_override_in_per_pt=scale_override_in_per_pt,
        )
    else:
        plan = parse_raster_page(
            pdf_path,
            page_index,
            project_name=project_name,
            level_name=level_name,
            config=VisionConfig(
                model=vision_cfg_dict.get("model", ""),
                fallback_model=vision_cfg_dict.get("fallback_model", ""),
                image_dpi=int(vision_cfg_dict.get("image_dpi", 200)),
                max_pages=int(vision_cfg_dict.get("max_pages_per_pdf", 20)),
                provider=vision_provider or vision_cfg_dict.get("provider", ""),
            ),
            reference_pdf=reference_pdf,
            reference_page_index=reference_page_index,
            anchor_bbox_override=anchor_bbox_override,
            refine_anchor=refine_anchor,
        )

    # Run accuracy verification — compares dimension callouts to measured geometry.
    check_plan_accuracy(plan)

    return plan
