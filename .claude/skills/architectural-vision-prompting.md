---
name: architectural-vision-prompting
description: How to instruct a vision model (Claude, Gemini, GPT) to read architectural floor plans accurately — image-normalized coordinate convention, calibration via dimension callouts, drawing-area bbox, drafter persona prefix, structured JSON schema. Invoke whenever building prompts for vision-model plan analysis, or troubleshooting why a vision pass produced wrong geometry.
---

# Architectural Vision Prompting Skill

How to get a vision model to read an architectural floor plan correctly. This is the prompt-engineering knowledge accumulated from running Claude Sonnet 4.5, Gemini 2.5 Pro/Flash, and OpenAI GPT-4o against real floor plans.

Authoritative reference: `src/ingest/vision_parser.py::SYSTEM_PROMPT`. Persona file: `config/drafting/drafter_persona.txt`.

---

## Why vision models hallucinate floor plans

Two failure modes dominate. Both have fixes.

### Failure 1: AI invents plausible-but-wrong coordinates

When asked for `walls[].x0_in` etc., the model returns numbers that LOOK reasonable but don't actually match the image. Architectural plans contain too many similar-looking rectangles for token-level visual reasoning to measure precisely.

**Fix**: Don't ask for real-world inches. Ask for **image-normalized coordinates** in `[0, 1]` × `[0, 1]`, then derive inches from a single calibration dimension.

### Failure 2: AI ignores part of the plan

When the image is downsized (Claude downscales to ~1568px on longest edge, Gemini to ~3072), small labels become unreadable. The model defaults to labeling clear areas and omitting the rest.

**Fix**: Make the model report `drawing_area_norm_bbox` explicitly. If it returns a generic `[0.05, 0.05, 0.95, 0.95]`, prompt it for a SECOND focused pass on the bbox alone.

---

## The image-norm coordinate convention

Tell the model:

> All geometric coordinates are in normalized image-pixel space:
> - Origin (0, 0) = **TOP-LEFT** corner of the image
> - (1, 1) = bottom-right
> - +X right, +Y down (image convention)
> - Coordinates are floats in [0, 1]
>
> DO NOT convert to inches yourself. The caller converts pixel coords to real-world inches using ONE calibration dimension you also provide.

This works because:

1. The model is good at visual position estimation in pixel space.
2. The model has no concept of "what 1 inch looks like" in pixels.
3. Calibration is a separate single number that anchors the whole plan.

---

## The calibration block

Ask explicitly for a calibration object:

```json
{
  "calibration": {
    "text": "27'-5\"",
    "value_in": 329.0,
    "point_a": [0.13, 0.42],
    "point_b": [0.78, 0.42]
  }
}
```

`point_a` and `point_b` are in image-norm space. `value_in` is the real-world inches. The caller derives:

```python
inches_per_norm = value_in / hypot(p_b - p_a)
real_world_in = norm * inches_per_norm
```

Prompt rules:

1. Tell the model to pick ONE dimension callout it can read clearly. Larger dimensions give better calibration (less relative pixel-error in endpoint estimation).
2. Tell it to set `value_in = 0` if it cannot find any dimension callout — never invent one.
3. The caller picks a default (1/4" = 1'-0") when calibration is missing.

---

## The drawing-area bbox

Critical for sheets with multiple drawings or large title blocks:

```json
{
  "drawing_area_norm_bbox": [0.06, 0.04, 0.84, 0.96]
}
```

This is the bbox that tightly encloses the floor plan, EXCLUDING title block, legend, north arrow, scale bar, schedules, and dimension callouts outside the perimeter walls.

Prompt rules:

1. "Padding > 2% is wrong; err tighter not looser."
2. "If you are uncertain, return your best estimate — a generic guess is worse than tighter wrong."
3. If the model returns something like `[0.02, 0.02, 0.98, 0.98]`, treat it as a "I didn't really look" signal and run a focused second-pass refinement.

---

## Two-pass anchor refinement

If the main extraction pass returns a loose bbox, run a focused second call with ONLY the bbox question:

```
SYSTEM:
You will receive a single image — a PDF page with a floor plan plus
(usually) title block, legend, schedules.

Your ONLY job: return the normalized pixel bounding box of the floor-plan
linework. Nothing else.

Return JSON: {"drawing_area_norm_bbox": [x0, y0, x1, y1]}

Rules:
- Top-left = (0, 0); bottom-right = (1, 1).
- TIGHTLY enclose every wall in the floor plan.
- EXCLUDE title block, legend, north arrow, scale bar, room schedules.
- Padding > 2% is incorrect.
```

Replace the original bbox only if the refined one is at least 5% smaller on either dimension (i.e., it's actually tighter). The implementation in `vision_parser.py::refine_anchor_bbox` does exactly this.

---

## The drafter persona

Prepend a "you are a 20-year drafter" persona to the system prompt. The persona changes the response distribution measurably:

- Median dimension error drops by ~5×.
- Doors/windows get distinguished where before everything was "door."
- Material callouts (LVT, Tile, ACT) appear instead of being silently omitted.

The persona content lives at `config/drafting/drafter_persona.txt`. Inject it via `vision_parser.py::_load_drafter_persona`. Update it whenever you tighten standards.

Persona must include:

1. Authoritative references (AIA, NCS, ISO 128, Architectural Graphic Standards).
2. Layer-assignment rules (walls = 0.50 mm CONTINUOUS on A-WALL).
3. Geometric defaults (plan-cut at 4'-0" AFF).
4. Standard scale set (only the canonical list).
5. NCS sheet identifier format.
6. **"You do NOT guess dimensions."** — explicit anti-hallucination rule.

---

## Structured JSON output schema

Require the model to return only JSON, with a fixed schema:

```json
{
  "level_name": "Ground Floor",
  "scale_note": "1/4\" = 1'-0\"",
  "drawing_area_norm_bbox": [x0, y0, x1, y1],
  "calibration": {
    "text": "...", "value_in": 0.0,
    "point_a": [x, y], "point_b": [x, y]
  },
  "walls": [
    {"p0": [x, y], "p1": [x, y], "thickness_norm": float, "status": "..."}
  ],
  "openings": [
    {"center": [x, y], "width_norm": float, "kind": "Door|Window|Opening",
     "swing": "left|right|null", "sill_height_norm": float}
  ],
  "rooms": [
    {"name": "...", "polygon": [[x, y], ...],
     "floor_finish": "...", "ceiling_finish": "...", "ceiling_height_in": float}
  ],
  "fixtures": [
    {"kind": "Casework|Plumbing Fixture|Equipment|...",
     "name": "...", "bbox_min": [x, y], "bbox_max": [x, y], "rotation_deg": float}
  ],
  "dimension_callouts": [
    {"text": "...", "value_in": float, "point_a": [x, y], "point_b": [x, y],
     "axis": "x|y|any"}
  ],
  "labels": [{"text": "...", "position": [x, y]}]
}
```

Notes:

1. Every field uses image-norm coords. Never mix in real-world inches.
2. Arrays are always present (empty if no items) — never omitted. Makes downstream parsing safer.
3. The fixture `kind` enum is explicit; no free-text categories.

---

## Provider-specific gotchas

### Claude (Anthropic)

- **Default max_tokens too low** — set 16384+ for big plans. The response can truncate mid-element, so the parser must handle partial JSON (see `_repair_truncated_json`).
- **Above ~8000 max_tokens, streaming is required** (10-min non-stream limit). Use `client.messages.stream()`.
- **Field-name drift** — Claude sometimes uses `p0/p1` instead of `x0_in/y0_in`, or `position` instead of `x_in/y_in`. The parser must tolerate variants.

### Gemini

- **Pro is rate-limited at 0 RPM on free tier** — billing required to use Pro reliably. Flash works but is less accurate.
- **Image downsizing happens silently** — large images get downscaled to ~3072px on long edge. Render at 200 DPI not higher; you'll just waste tokens.
- **JSON mode (`response_mime_type=application/json`) is helpful** — model is more likely to actually return JSON.

### OpenAI

- **Image detail = "high"** — required for plan reading at any reasonable size.
- **JSON mode via `response_format`** — required for structured output reliability.

---

## Token budget guidance

| Plan complexity | Output tokens budget |
|---|---|
| Single small room | 1,000 |
| Single floor plan, <10 rooms | 4,000 |
| Standard CD-set floor plan | 16,000 |
| Dense plan with full schedule annotations | 32,000+ |

Underbudgeting causes silent truncation. Overbudgeting wastes money. Tune per project.

---

## When to invoke

- Writing or editing the system prompt for a vision-model call
- Troubleshooting why a vision pass produced bad geometry
- Adding a new structured field to the JSON schema
- Switching between vision providers (Claude / Gemini / OpenAI)
- Designing two-pass refinement strategies
