"""Raster PDF page -> PlanGraph via Gemini Vision.

For raster/scanned/hand-drawn pages, we render each page to a PNG, then ask
Gemini to return a structured JSON description of the plan (rooms, walls,
openings, dimensions). That JSON is unmarshalled into a PlanGraph.

Costs and accuracy:
  * gemini-2.5-pro: best at architectural plan comprehension; more expensive
  * gemini-2.5-flash: ~10x cheaper, weaker on complex plans
  * Falls back to flash if pro fails or hits rate limits.

The system prompt is intentionally strict about output shape so the parser is
robust to model chatter.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .plan_model import (
    Annotation,
    DimensionCallout,
    Fixture,
    FixtureKind,
    IngestSource,
    Opening,
    OpeningKind,
    PageMeta,
    PlanGraph,
    Point,
    Room,
    Wall,
    WallStatus,
)

logger = logging.getLogger(__name__)


def _load_drafter_persona() -> str:
    """Load the seasoned-drafter persona from disk.

    Falls back to an empty string if the file is missing so the pipeline
    still runs without the drafting layer.
    """
    persona_path = (
        Path(__file__).resolve().parents[2]
        / "config" / "drafting" / "drafter_persona.txt"
    )
    if persona_path.exists():
        return persona_path.read_text().rstrip() + "\n\n"
    return ""


SYSTEM_PROMPT = _load_drafter_persona() + """\
You are an expert architectural plan reader. The user will provide an image of
a floor plan. Return ONLY a single JSON object describing the plan, with no
prose, markdown, or commentary.

GOAL: produce data accurate enough to rebuild this floor in BIM.

# COORDINATE SYSTEM — READ CAREFULLY

ALL geometric coordinates in your response are in **normalized image-pixel
space**:
  * Origin (0, 0) = TOP-LEFT corner of the IMAGE you were given.
  * (1, 1) = bottom-right corner of the image.
  * +X right, +Y down (standard image convention).
  * Coordinates are floats in [0, 1].

DO NOT try to convert to inches yourself. Your job is to locate things in the
image. The caller converts image coords to real-world inches using ONE
calibration dimension you also provide.

# REQUIRED OUTPUT

Return a single JSON object with this shape. Every field required unless
marked optional:

{
  "level_name": string,
  "scale_note": string,    // optional — title-block scale text; "" if not shown

  "drawing_area_norm_bbox": [x0, y0, x1, y1],
       // Normalized image bbox that tightly encloses the floor plan
       // (walls). Exclude title block, legend, north arrow, scale bar,
       // schedules, dimensions outside the perimeter. Padding > 2% is wrong.

  "calibration": {
       // Pick ONE dimension callout visible on the plan that you can read
       // unambiguously (overall building width, a long room dimension, etc.).
       // Provide its TWO endpoints in IMAGE-NORM coords (the points the
       // dimension line spans between) and the value in real-world inches.
       // This is how we anchor everything else to real-world scale.
       // If you cannot find any dimension callout, set value_in=0.
       "text": string,           // e.g. "27'-5\\""
       "value_in": float,        // parsed real-world inches; 0 = unknown
       "point_a": [x, y],        // image-norm endpoint
       "point_b": [x, y]
  },

  "walls": [
       // STRAIGHT segments only. Split any curves.
    {
      "p0": [x, y],              // image-norm
      "p1": [x, y],
      "thickness_norm": float,   // thickness in image-norm units (small)
      "status": "Existing" | "Demolition" | "New Construction"
    }
  ],

  "openings": [
       // Doors, windows, and cased openings — look HARD for windows.
    {
      "center": [x, y],          // image-norm, on the parent wall
      "width_norm": float,       // image-norm width along the wall
      "kind": "Door" | "Window" | "Opening",
      "swing": "left" | "right" | null,
      "sill_height_norm": float  // 0 for doors; ~0.03 typical for windows
    }
  ],

  "rooms": [
    {
      "name": string,            // exactly as labeled on the plan
      "polygon": [[x, y], ...],  // ordered closed polygon in image-norm
      "floor_finish": string,    // "LVT","Tile","Carpet","Wood","Concrete",""
      "ceiling_finish": string,  // "ACT","GWB Painted","Open Structure",""
      "ceiling_height_in": float // 0 if not shown
    }
  ],

  "fixtures": [
       // BUILT-IN / stationary only. NO movable furniture.
       // INCLUDE: casework, counters, sinks, toilets, tubs, fixed equipment,
       //   reception desks, built-in fridges, built-in kennels, columns,
       //   stairs.
       // EXCLUDE: chairs, tables, free-standing shelves, exam stools, beds.
    {
      "kind": "Casework" | "Plumbing Fixture" | "Equipment" | "Appliance"
            | "Reception Desk" | "Exam Table" | "Kennel Run" | "Column"
            | "Stair" | "Other Built-in",
      "name": string,
      "bbox_min": [x, y],        // image-norm bounding box, axis-aligned
      "bbox_max": [x, y],
      "rotation_deg": float
    }
  ],

  "dimension_callouts": [
       // Every visible dimension callout, including the one you used for
       // calibration. Same image-norm endpoints + real-world value.
    {
      "text": string,
      "value_in": float,
      "point_a": [x, y],
      "point_b": [x, y],
      "axis": "x" | "y" | "any"
    }
  ],

  "labels": [
    {"text": string, "position": [x, y]}
  ]
}

# RULES

* All coordinates in [0, 1] image-norm space. Top-left origin.
* DO NOT emit nulls inside numeric fields. Use 0 if unknown.
* If a key has no items, return an empty array — never omit it.
* Walls are straight line segments. Split curves into segments.
* When placing geometry, derive coordinates by visually MEASURING positions
  in the image. Do NOT make up coordinates that look plausible.
"""


@dataclass
class VisionConfig:
    """Provider-agnostic vision config.

    ``model``/``fallback_model`` are forwarded to whatever vision provider is
    selected (Gemini / Anthropic / OpenAI). If left at the defaults, each
    provider uses its own sensible primary/fallback pair.
    """
    model: str = ""
    fallback_model: str = ""
    image_dpi: int = 200
    max_pages: int = 20
    provider: str = ""              # "" = auto-detect (see vision_providers)


ANCHOR_SYSTEM_PROMPT = """\
You will receive a single image: a PDF page that contains an architectural
floor plan, plus (usually) a title block, legend, and ancillary text.

Your ONLY job: return the normalized pixel bounding box of the floor-plan
linework (walls / partitions / rooms) within that image. Nothing else.

Return JSON of the form:
{"drawing_area_norm_bbox": [x0, y0, x1, y1]}

Rules:
  * Coordinates are normalized to image dimensions: top-left = (0,0),
    bottom-right = (1,1). +X right, +Y down.
  * The bbox must TIGHTLY enclose every wall in the floor plan.
  * EXCLUDE title block, legend, north arrow, scale bar, room finish schedules,
    and any dimensioning that hangs outside the perimeter walls.
  * Padding of more than 2% on any side is incorrect.
  * If the image is mostly drawing area with no title block, return
    [0.02, 0.02, 0.98, 0.98] (tight against image edges).
  * Output ONLY the JSON — no prose, no markdown.
"""


def parse_raster_page(
    pdf_path: str | Path,
    page_index: int,
    *,
    project_name: str = "",
    level_name: str = "Level 1",
    config: Optional[VisionConfig] = None,
    reference_pdf: Optional[str | Path] = None,
    reference_page_index: int = 0,
    anchor_bbox_override: Optional[list[float]] = None,
    refine_anchor: bool = True,
) -> PlanGraph:
    """Render one PDF page to PNG, send to Gemini, return a PlanGraph.

    If ``reference_pdf`` is supplied (e.g. a Matterport scan PDF), that image
    is included as an additional context image so the model can cross-check
    proportions and dimensions.
    """
    pdf_path = Path(pdf_path)
    cfg = config or VisionConfig()

    png_bytes = _render_pdf_page_to_png(pdf_path, page_index, dpi=cfg.image_dpi)

    ref_bytes = None
    if reference_pdf:
        ref_path = Path(reference_pdf)
        if ref_path.exists():
            ref_bytes = _render_pdf_page_to_png(ref_path, reference_page_index, dpi=cfg.image_dpi)
            logger.info("Including reference PDF %s page %d as context.",
                        ref_path.name, reference_page_index)
        else:
            logger.warning("reference_pdf %s does not exist; ignoring.", ref_path)

    provider = _provider_for(cfg)
    raw_json = provider.parse_plan(
        png_bytes,
        system_prompt=SYSTEM_PROMPT,
        reference_bytes=ref_bytes,
        max_output_tokens=32768,
        temperature=0.1,
    )
    plan_dict = _extract_json(raw_json)

    plan = _dict_to_plan_graph(
        plan_dict,
        pdf_path=str(pdf_path),
        page_index=page_index,
        project_name=project_name,
        level_name_default=level_name,
    )

    # Apply manual override OR a focused second-pass anchor refinement.
    if anchor_bbox_override is not None and len(anchor_bbox_override) == 4:
        if plan.page is not None:
            plan.page.drawing_area_norm_bbox = [
                max(0.0, min(1.0, float(v))) for v in anchor_bbox_override
            ]
            logger.info("Anchor bbox overridden manually: %s",
                        plan.page.drawing_area_norm_bbox)
    elif refine_anchor and plan.page is not None:
        try:
            refined = refine_anchor_bbox(png_bytes, cfg)
            if refined is not None and _looks_tighter(refined, plan.page.drawing_area_norm_bbox):
                logger.info("Anchor refined %s -> %s",
                            plan.page.drawing_area_norm_bbox, refined)
                plan.page.drawing_area_norm_bbox = refined
        except Exception as exc:
            logger.warning("Anchor refinement call failed: %s", exc)

    return plan


def _provider_for(cfg: VisionConfig):
    """Return a VisionProvider instance configured per ``cfg``.

    Model overrides are only applied when they match the selected provider's
    naming convention (so a stale ``gemini-2.5-pro`` default from
    config/ingest.json doesn't leak into the Anthropic / OpenAI providers).
    """
    from .vision_providers import get_provider
    from .vision_providers.base import ModelChoice

    p = get_provider(cfg.provider or None)
    if cfg.model or cfg.fallback_model:
        primary = cfg.model or cfg.fallback_model
        if _model_matches_provider(primary, p.name):
            p.models = ModelChoice(
                primary=primary,
                fallback=cfg.fallback_model or primary,
            )
    return p


def _model_matches_provider(model_name: str, provider_name: str) -> bool:
    """Heuristic: does ``model_name`` belong to ``provider_name``?"""
    m = model_name.lower()
    if provider_name == "gemini":
        return m.startswith("gemini")
    if provider_name == "anthropic":
        return m.startswith("claude")
    if provider_name == "openai":
        return m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")
    return False


def refine_anchor_bbox(image_bytes: bytes, cfg: VisionConfig) -> Optional[list[float]]:
    """Focused second-pass call that returns ONLY the drawing-area bbox.

    Uses the dedicated ANCHOR_SYSTEM_PROMPT through the configured provider.
    Returns ``None`` if the response couldn't be parsed.
    """
    try:
        provider = _provider_for(cfg)
    except Exception as exc:
        logger.warning("No vision provider for anchor refinement: %s", exc)
        return None

    try:
        text = provider.refine_anchor(
            image_bytes,
            system_prompt=ANCHOR_SYSTEM_PROMPT,
        )
    except Exception as exc:
        logger.warning("Anchor provider call failed: %s", exc)
        return None

    if not text:
        return None
    try:
        parsed = _extract_json(text)
    except Exception:
        return None
    bbox = parsed.get("drawing_area_norm_bbox")
    if not bbox or len(bbox) != 4:
        return None
    clamped = [max(0.0, min(1.0, float(v))) for v in bbox]
    if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
        return None
    return clamped


def _looks_tighter(new_bbox: list[float], old_bbox: Optional[list[float]]) -> bool:
    """Return True if ``new_bbox`` is at least 5% smaller on either dimension."""
    if not old_bbox:
        return True
    nw = new_bbox[2] - new_bbox[0]
    nh = new_bbox[3] - new_bbox[1]
    ow = old_bbox[2] - old_bbox[0]
    oh = old_bbox[3] - old_bbox[1]
    return nw * nh < ow * oh * 0.95


# ---------------------------------------------------------------------------
# PDF -> PNG
# ---------------------------------------------------------------------------

def _render_pdf_page_to_png(pdf_path: Path, page_index: int, dpi: int) -> bytes:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ImportError(
            "pypdfium2 is required for raster ingest. Run: pip install pypdfium2"
        ) from exc

    pdf = pdfium.PdfDocument(pdf_path)
    if page_index < 0 or page_index >= len(pdf):
        raise IndexError(f"page_index {page_index} out of range")
    page = pdf[page_index]
    scale = dpi / 72.0
    pil_image = page.render(scale=scale).to_pil()

    import io
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# JSON -> PlanGraph
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """Parse the model's response, with progressive fallback for truncated JSON.

    Strategy:
      1. Strip ``` fences and parse as-is.
      2. If that fails, find the outermost ``{...}`` and try again.
      3. If still failing, attempt to repair common truncations:
         drop trailing partial elements/strings, close open braces/brackets.
    """
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    start = s.find("{")
    if start < 0:
        raise ValueError(f"No JSON object found in model output: {s[:300]}")
    s = s[start:]

    # Try direct parse of the trimmed block.
    try:
        return json.loads(s)
    except json.JSONDecodeError as exc:
        # Progressive truncation repair: walk back from the failure point,
        # trimming until we hit a place we can balance braces/brackets.
        repaired = _repair_truncated_json(s, exc.pos)
        if repaired is not None:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # Last resort: keep walking back and try repairs.
        for cut in range(exc.pos, max(0, exc.pos - 5000), -50):
            repaired = _repair_truncated_json(s[:cut], cut)
            if repaired is None:
                continue
            try:
                logger.warning("Gemini JSON was malformed; recovered partial response "
                               "(truncated at offset %d).", cut)
                return json.loads(repaired)
            except json.JSONDecodeError:
                continue
        raise ValueError(
            f"Could not parse Gemini JSON even with repair: {exc}\n"
            f"--- first 500 chars ---\n{s[:500]}\n"
            f"--- last 500 chars ---\n{s[-500:]}"
        )


def _repair_truncated_json(s: str, cutoff: int) -> Optional[str]:
    """Attempt to close brackets/braces in a truncated JSON string.

    Walks the string, marks every "safe cut" position (where a value at any
    depth could legitimately end), then iterates from the latest safe cut
    backward — at each one, count remaining open brackets/braces and try to
    close them. First candidate that parses cleanly wins.
    """
    if not s:
        return None
    text = s[:cutoff] if cutoff < len(s) else s

    # First, build a list of safe cut positions (end of a complete value).
    safe_cuts: list[int] = []
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                safe_cuts.append(i + 1)
            continue
        if ch == '"':
            in_string = True
        elif ch in "}]":
            safe_cuts.append(i + 1)
        elif ch == ",":
            safe_cuts.append(i)  # cut BEFORE the comma

    # Walk from latest to earliest safe cut; first balanced+parseable wins.
    for cut in reversed(safe_cuts):
        cut_text = text[:cut].rstrip()
        if not cut_text or not cut_text.startswith("{"):
            continue
        d_curly = 0
        d_square = 0
        in_str = False
        esc = False
        ok = True
        for ch in cut_text:
            if esc:
                esc = False
                continue
            if in_str:
                if ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                d_curly += 1
            elif ch == "}":
                d_curly -= 1
            elif ch == "[":
                d_square += 1
            elif ch == "]":
                d_square -= 1
            if d_curly < 0 or d_square < 0:
                ok = False
                break
        if not ok or in_str:
            continue
        candidate = cut_text + ("]" * d_square) + ("}" * d_curly)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue
    return None


def _pick(d: dict, *keys, default=None):
    """Return the first present, non-None value from ``d`` for any of ``keys``.

    Models vary slightly in field names — this is the tolerance boundary.
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _resolve_calibration(d: dict) -> tuple[float, str, float]:
    """Pick the most-trustworthy dimension to anchor the image-norm → inches scale.

    Returns (inches_per_norm, calibration_text, calibration_value_in).

    Strategy:
      1. Use the model's dedicated ``calibration`` block if it gave one.
      2. Otherwise, scan ``dimension_callouts`` for the LONGEST callout with
         well-formed endpoints; longest = lowest relative measurement error.
      3. If neither is usable, fall back to inches_per_norm=240 (assume
         the plan is roughly 240" = 20' wide). This gives broken geometry
         but at least the pipeline produces output that flags the issue.
    """
    import math as _math

    def from_two_points(pa, pb, value_in) -> Optional[float]:
        if not pa or not pb or value_in <= 0:
            return None
        pa_xy = _coerce_xy(pa) or (0.0, 0.0)
        pb_xy = _coerce_xy(pb) or (0.0, 0.0)
        dist_norm = _math.hypot(pb_xy[0] - pa_xy[0], pb_xy[1] - pa_xy[1])
        if dist_norm < 0.005:
            return None
        return value_in / dist_norm

    calib = d.get("calibration") or {}
    text = str(calib.get("text", ""))
    try:
        value_in = float(calib.get("value_in", 0.0) or 0.0)
    except (TypeError, ValueError):
        value_in = 0.0
    ipn = from_two_points(calib.get("point_a"), calib.get("point_b"), value_in)
    if ipn:
        logger.info("Calibration from explicit block: %s = %s in → %.2f in/norm",
                    text, value_in, ipn)
        return ipn, text, value_in

    # Fallback: scan dimension_callouts for the longest usable one.
    best = None  # (ipn, text, value)
    best_len = 0.0
    for dc in d.get("dimension_callouts", []) or []:
        try:
            v = float(_pick(dc, "value_in", "value", "length_in", default=0.0) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        if v <= 0:
            continue
        pa = _coerce_xy(_pick(dc, "point_a", "start", "a"))
        pb = _coerce_xy(_pick(dc, "point_b", "end", "b"))
        if not pa or not pb:
            continue
        d_n = _math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if d_n < 0.05:
            continue
        ipn = v / d_n
        if v > best_len:
            best_len = v
            best = (ipn, str(dc.get("text", "")), v)

    if best:
        logger.info("Calibration from largest dim callout: %s = %s in → %.2f in/norm",
                    best[1], best[2], best[0])
        return best

    logger.warning("No calibration available; assuming 240 in/norm (20-ft plan width). "
                   "Geometry will be qualitatively but not quantitatively accurate.")
    return 240.0, "", 0.0


def _geometry_norm_bbox(d: dict) -> tuple[float, float, float, float]:
    """Image-norm bounding box of all wall / room / fixture coords in the response."""
    xs: list[float] = []
    ys: list[float] = []

    def absorb(p):
        xy = _coerce_xy(p)
        if xy is None:
            return
        xs.append(xy[0])
        ys.append(xy[1])

    for w in d.get("walls", []) or []:
        absorb(_pick(w, "p0", "start", "a"))
        absorb(_pick(w, "p1", "end", "b"))
    for r in d.get("rooms", []) or []:
        for p in r.get("polygon", []) or []:
            absorb(p)
    for fx in d.get("fixtures", []) or []:
        absorb(_pick(fx, "bbox_min", "min"))
        absorb(_pick(fx, "bbox_max", "max"))
    if not xs:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _coerce_xy(value) -> Optional[tuple[float, float]]:
    """Coerce a value into an (x, y) tuple, handling list/tuple/dict shapes."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict):
        try:
            return float(value.get("x", 0)), float(value.get("y", 0))
        except (TypeError, ValueError):
            return None
    return None


def _extract_fixture_bbox(fx: dict) -> tuple[Point, Point]:
    """Pull a fixture's axis-aligned bbox out of whatever shape the model gave.

    Accepted formats (first that resolves wins):
      * bbox_min + bbox_max as [x,y] or {x:,y:}
      * x0_in/y0_in/x1_in/y1_in
      * center_x_in/center_y_in + width_in + depth_in (or height_in)
      * position {x,y} + width_in + depth_in
      * size {w,h} alongside position
    """
    bmin = _coerce_xy(_pick(fx, "bbox_min", "min", "lower_left"))
    bmax = _coerce_xy(_pick(fx, "bbox_max", "max", "upper_right"))
    if bmin and bmax:
        return Point(x=bmin[0], y=bmin[1]), Point(x=bmax[0], y=bmax[1])

    # Two-corner explicit fields.
    has_corners = all(k in fx for k in ("x0_in", "y0_in", "x1_in", "y1_in"))
    if has_corners:
        return (
            Point(x=float(fx["x0_in"]), y=float(fx["y0_in"])),
            Point(x=float(fx["x1_in"]), y=float(fx["y1_in"])),
        )

    # Center + size.
    cx = _pick(fx, "center_x_in", "cx_in", "x_in", "x")
    cy = _pick(fx, "center_y_in", "cy_in", "y_in", "y")
    if cx is None or cy is None:
        pos = _coerce_xy(fx.get("position"))
        if pos:
            cx, cy = pos
    width = _pick(fx, "width_in", "width", "w")
    depth = _pick(fx, "depth_in", "depth", "d", "height_in_plan", "size_y_in")
    if cx is not None and cy is not None and width and depth:
        cx = float(cx); cy = float(cy)
        hw = float(width) / 2.0
        hd = float(depth) / 2.0
        return (
            Point(x=cx - hw, y=cy - hd),
            Point(x=cx + hw, y=cy + hd),
        )

    # Size as a {w,h} dict.
    size = fx.get("size")
    if isinstance(size, dict) and cx is not None and cy is not None:
        hw = float(size.get("w", size.get("width", 0))) / 2.0
        hd = float(size.get("h", size.get("depth", size.get("height", 0)))) / 2.0
        cx = float(cx); cy = float(cy)
        return (
            Point(x=cx - hw, y=cy - hd),
            Point(x=cx + hw, y=cy + hd),
        )

    # Could not resolve — return zero-sized bbox so the caller can skip it.
    return Point(x=0.0, y=0.0), Point(x=0.0, y=0.0)


def _pick_point(d: dict, base: str) -> tuple[float, float]:
    """Pick (x, y) from a dict using several possible key conventions.

    base="0" probes x0_in/y0_in/x0/y0/start_x_in/start_y_in/... etc.
    """
    xkey_options = (f"x{base}_in", f"x{base}", f"{base}_x_in", f"{base}_x")
    ykey_options = (f"y{base}_in", f"y{base}", f"{base}_y_in", f"{base}_y")
    if base == "":
        xkey_options = ("x_in", "x", "cx_in", "cx", "x_center_in", "center_x_in")
        ykey_options = ("y_in", "y", "cy_in", "cy", "y_center_in", "center_y_in")
    x = _pick(d, *xkey_options, default=0.0)
    y = _pick(d, *ykey_options, default=0.0)
    try:
        return float(x), float(y)
    except (TypeError, ValueError):
        return 0.0, 0.0


def _dict_to_plan_graph(
    d: dict,
    *,
    pdf_path: str,
    page_index: int,
    project_name: str,
    level_name_default: str,
) -> PlanGraph:
    # ── Calibration: derive inches-per-norm from the model's calibration dim.
    inches_per_norm, calib_text, calib_value = _resolve_calibration(d)

    def n2in(p: tuple[float, float]) -> tuple[float, float]:
        """Image-norm (top-left origin, +Y down) → real-world inches (bottom-left, +Y up)."""
        x_norm, y_norm = p
        x_in = x_norm * inches_per_norm
        y_in = (1.0 - y_norm) * inches_per_norm
        return x_in, y_in

    walls: list[Wall] = []
    for w in d.get("walls", []) or []:
        status_str = (w.get("status") or "Existing").strip()
        status = {
            "Existing": WallStatus.EXISTING,
            "Demolition": WallStatus.DEMOLITION,
            "New Construction": WallStatus.NEW,
        }.get(status_str, WallStatus.EXISTING)
        p0n = _coerce_xy(_pick(w, "p0", "start", "a")) or _pick_point(w, "0")
        p1n = _coerce_xy(_pick(w, "p1", "end", "b")) or _pick_point(w, "1")
        x0, y0 = n2in(p0n)
        x1, y1 = n2in(p1n)
        thickness_norm = float(_pick(w, "thickness_norm", "thickness_in",
                                     "thickness", default=0.005))
        # If model still sent thickness_in directly, treat values >=1 as already inches.
        thickness_in = thickness_norm if thickness_norm >= 1.0 else thickness_norm * inches_per_norm
        # Clamp to reasonable wall thickness (2"–14")
        thickness_in = max(2.5, min(14.0, thickness_in)) if inches_per_norm > 0 else 4.5
        walls.append(Wall(
            id=f"w-{uuid.uuid4().hex[:8]}",
            start=Point(x=x0, y=y0),
            end=Point(x=x1, y=y1),
            thickness_in=thickness_in,
            status=status,
            confidence=0.75,
            source_note=f"vision_norm:{p0n}->{p1n}",
        ))

    # Vision openings reference absolute coordinates; we attach them to the
    # nearest wall in normalize_openings (geometry_normalizer can run again, or
    # we just keep them floating for now with wall_id="" and resolve in build).
    openings: list[Opening] = []
    for o in d.get("openings", []) or []:
        kind = {
            "Door": OpeningKind.DOOR,
            "Window": OpeningKind.WINDOW,
            "Opening": OpeningKind.OPENING,
        }.get((o.get("kind") or "Door").strip(), OpeningKind.DOOR)
        center_n = _coerce_xy(_pick(o, "center", "position")) or _pick_point(o, "")
        op_x, op_y = n2in(center_n)
        wall_id, dist = _attach_to_nearest_wall(op_x, op_y, walls)
        width_norm = float(_pick(o, "width_norm", "width_in", "width", default=0.0))
        width_in = width_norm if width_norm >= 1.0 else width_norm * inches_per_norm
        width_in = width_in if width_in >= 12 else 36.0
        sill_norm = float(_pick(o, "sill_height_norm", "sill_height_in",
                                "sill_height", default=0.0))
        sill_in = sill_norm if sill_norm >= 1.0 else sill_norm * inches_per_norm
        openings.append(Opening(
            id=f"o-{uuid.uuid4().hex[:8]}",
            wall_id=wall_id,
            distance_along_wall_in=dist,
            width_in=width_in,
            sill_height_in=sill_in,
            kind=kind,
            swing_direction=o.get("swing"),
            confidence=0.7,
        ))

    rooms: list[Room] = []
    for r in d.get("rooms", []) or []:
        poly_inches = []
        for p in r.get("polygon", []) or []:
            xy = _coerce_xy(p)
            if xy is None:
                continue
            xi, yi = n2in(xy)
            poly_inches.append(Point(x=xi, y=yi))
        rooms.append(Room(
            id=f"r-{uuid.uuid4().hex[:8]}",
            name=str(r.get("name", "")),
            polygon=poly_inches,
            area_sqft=_polygon_area_sqft(poly_inches),
            floor_finish=str(r.get("floor_finish", "")),
            ceiling_finish=str(r.get("ceiling_finish", "")),
            ceiling_height_in=float(r.get("ceiling_height_in", 0.0) or 0.0),
            confidence=0.7,
        ))

    fixtures: list[Fixture] = []
    for fx in d.get("fixtures", []) or []:
        try:
            kind_str = (fx.get("kind") or "Other Built-in").strip()
            kind = FixtureKind(kind_str)
        except ValueError:
            kind = FixtureKind.OTHER
        bmin_pt_norm, bmax_pt_norm = _extract_fixture_bbox(fx)
        # Convert each corner from image-norm to real-world inches.
        # NOTE: y-flip means image-norm bbox_min (top-left) maps to inches bbox_max (top).
        x0, y0 = n2in((bmin_pt_norm.x, bmin_pt_norm.y))
        x1, y1 = n2in((bmax_pt_norm.x, bmax_pt_norm.y))
        # Normalize so bbox_min has the smaller of each coord.
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        fixtures.append(Fixture(
            id=f"f-{uuid.uuid4().hex[:8]}",
            kind=kind,
            name=str(fx.get("name", "")),
            bbox_min=Point(x=xmin, y=ymin),
            bbox_max=Point(x=xmax, y=ymax),
            rotation_deg=float(_pick(fx, "rotation_deg", "rotation", default=0.0) or 0.0),
            confidence=0.65,
        ))

    dim_callouts: list[DimensionCallout] = []
    for dc in d.get("dimension_callouts", []) or []:
        pa_n = _coerce_xy(_pick(dc, "point_a", "start", "a", "p1")) or (0.0, 0.0)
        pb_n = _coerce_xy(_pick(dc, "point_b", "end", "b", "p2")) or (0.0, 0.0)
        try:
            value_in = float(_pick(dc, "value_in", "value", "length_in", default=0.0) or 0.0)
        except (TypeError, ValueError):
            value_in = 0.0
        if value_in <= 0:
            continue
        pa_xy = n2in(pa_n)
        pb_xy = n2in(pb_n)
        lp = ((pa_xy[0] + pb_xy[0]) / 2.0, (pa_xy[1] + pb_xy[1]) / 2.0)
        dim_callouts.append(DimensionCallout(
            id=f"d-{uuid.uuid4().hex[:8]}",
            text=str(dc.get("text", "")),
            value_in=value_in,
            point_a=Point(x=pa_xy[0], y=pa_xy[1]),
            point_b=Point(x=pb_xy[0], y=pb_xy[1]),
            label_position=Point(x=lp[0], y=lp[1]),
            axis=str(dc.get("axis", "any")),
        ))

    annotations: list[Annotation] = []
    for lbl in d.get("labels", []) or []:
        pos_n = _coerce_xy(_pick(lbl, "position", "pos")) or _pick_point(lbl, "")
        lx, ly = n2in(pos_n)
        annotations.append(Annotation(
            id=f"a-{uuid.uuid4().hex[:8]}",
            text=str(lbl.get("text", "")),
            position=Point(x=lx, y=ly),
        ))

    bbox = d.get("plan_bbox_in") or {}
    draw_bbox = d.get("drawing_area_norm_bbox") or None
    if isinstance(draw_bbox, list) and len(draw_bbox) == 4:
        draw_bbox = [float(v) for v in draw_bbox]
        draw_bbox = [max(0.0, min(1.0, v)) for v in draw_bbox]
    else:
        draw_bbox = None

    # Compute the image-norm bbox of all detected geometry — this is what the
    # overlay uses to position the SVG on the source PDF.
    geom_norm = _geometry_norm_bbox(d)

    page_meta = PageMeta(
        page_index=page_index,
        source_pdf=pdf_path,
        width_in=float(bbox.get("width", 0.0)) or (geom_norm[2] - geom_norm[0]) * inches_per_norm,
        height_in=float(bbox.get("height", 0.0)) or (geom_norm[3] - geom_norm[1]) * inches_per_norm,
        detected_scale_text=str(d.get("scale_note", "")),
        is_vector=False,
        confidence=0.7,
        drawing_area_norm_bbox=draw_bbox,
        inches_per_norm=inches_per_norm,
        geom_norm_bbox=list(geom_norm) if geom_norm else None,
        calibration_dim_text=calib_text,
        calibration_dim_in=calib_value,
    )

    plan = PlanGraph(
        project_name=project_name,
        level_name=str(d.get("level_name") or level_name_default),
        units="imperial",
        source=IngestSource.VISION,
        page=page_meta,
        walls=walls,
        openings=openings,
        rooms=rooms,
        fixtures=fixtures,
        annotations=annotations,
        dimension_callouts=dim_callouts,
    )

    if not walls:
        plan.warnings.append("Vision parser returned no walls — review the page image.")
    if any(o.wall_id == "" for o in openings):
        plan.warnings.append("Some openings could not be attached to a wall.")

    return plan


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _attach_to_nearest_wall(x: float, y: float, walls: list[Wall]) -> tuple[str, float]:
    """Return (wall_id, distance_along_wall_in) for the nearest wall, or ('', 0)."""
    best_id = ""
    best_dist_to_wall = math.inf
    best_t = 0.0
    for w in walls:
        ax, ay = w.start.x, w.start.y
        bx, by = w.end.x, w.end.y
        wx, wy = bx - ax, by - ay
        wlen_sq = wx * wx + wy * wy
        if wlen_sq < 1e-6:
            continue
        t = max(0.0, min(1.0, ((x - ax) * wx + (y - ay) * wy) / wlen_sq))
        px = ax + t * wx
        py = ay + t * wy
        d = math.hypot(x - px, y - py)
        if d < best_dist_to_wall:
            best_dist_to_wall = d
            best_id = w.id
            best_t = t * math.sqrt(wlen_sq)
    return best_id, best_t


def _polygon_area_sqft(poly: list[Point]) -> float:
    if len(poly) < 3:
        return 0.0
    area_sq_in = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i].x, poly[i].y
        x1, y1 = poly[(i + 1) % n].x, poly[(i + 1) % n].y
        area_sq_in += x0 * y1 - x1 * y0
    return abs(area_sq_in) / 2.0 / 144.0
