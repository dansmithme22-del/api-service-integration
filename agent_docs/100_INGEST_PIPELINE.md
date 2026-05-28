# Ingest → Build → Render Pipeline

## Context-switch recap (10 bullets)

1. The pipeline adds **Layer 0** (`src/ingest/`) before the existing
   Extract → Decide → Apply flow.
2. Layer 0 turns a reference PDF (vector or raster) into a `PlanGraph`
   (walls + openings + rooms + annotations in real-world inches).
3. The new **build** layer (`src/build/`) materialises a `PlanGraph` into
   Archicad elements over the JSON API, or emits a JSON "command tape"
   for offline review.
4. The new **revise** layer (`src/revise/`) takes a natural-language
   revision request + an existing `PlanGraph` and returns a new
   `PlanGraph` plus a `ChangeLog`.
5. The new **render** layer (`src/render/`) pulls Archicad view PNGs
   (filesystem or Publisher Set) and sends each through Gemini 2.5
   Flash Image with a configurable style prompt.
6. `config/ingest.json` holds all thresholds: vector/raster cutoff,
   wall-pair geometry tolerances, vision model selection, default
   wall layers, render prompt.
7. Secrets go in a local `.env` (gitignored). Code reads
   `GEMINI_API_KEY` via `os.environ`.
8. Vector PDFs route through `pdfplumber` → line/arc/text extraction →
   wall-pairing → `PlanGraph`. Raster PDFs route through `pypdfium2` →
   PNG → Gemini 2.5 Pro/Flash → structured JSON → `PlanGraph`.
9. The Archicad builder always writes a JSON tape; live execution is
   opt-in (`--apply`). Tape format mirrors `API.CreateElements`.
10. Run `pytest tests/test_ingest.py` for fast, offline verification of
    the geometry math and tape serialisation.

---

## Architecture

```
                          ┌──────────────────┐
   Reference PDF  ───────►│  src/ingest      │  PlanGraph (JSON)
   (vector/raster)        │  (Layer 0)       │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
   Revision request ─────►│  src/revise      │  PlanGraph + ChangeLog
   ("remove wall X")      │  (optional)      │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  src/build       │  Archicad command tape
                          │  → Archicad      │  (or live elements)
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  src/extract     │  existing pipeline
                          │  src/decide      │  (sheet notes)
                          │  src/apply       │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
   Saved views ──────────►│  src/render      │  Photoreal PNGs
   (Archicad/Publisher)   │  (Gemini)        │
                          └──────────────────┘
```

## Data flow

| Stage | Input | Output |
|---|---|---|
| `ingest_pdf(path)` | PDF | `PlanGraph` |
| `apply_revision_request(plan, text)` | `PlanGraph` + NL text | `PlanGraph`, `ChangeLog` |
| `build_plan_in_archicad(plan, conn?)` | `PlanGraph` | tape JSON + (optional) AC elements |
| `export_views(dir, conn?)` | filesystem / Publisher Set | list of PNG paths |
| `render_image(src, dst)` | one PNG | one rendered PNG |

## Files

| File | Responsibility |
|---|---|
| `src/ingest/plan_model.py` | `PlanGraph`, `Wall`, `Opening`, `Room`, `Annotation`, `PageMeta` (Pydantic) |
| `src/ingest/pdf_classifier.py` | per-page vector-vs-raster verdict, floor-plan page picker |
| `src/ingest/vector_parser.py` | `pdfplumber` → `RawLine` / `RawArc` / `RawText` |
| `src/ingest/geometry_normalizer.py` | scale inference, wall-pairing, `RawPageGeometry` → `PlanGraph` |
| `src/ingest/vision_parser.py` | Gemini 2.5 Pro/Flash → strict JSON → `PlanGraph` |
| `src/ingest/runner.py` | `ingest_pdf()` orchestrator |
| `src/build/archicad_builder.py` | `PlanGraph` → tape entries → live `CreateElements` |
| `src/revise/interpreter.py` | `apply_revision_request()` + `ChangeLog` |
| `src/render/view_capturer.py` | scan filesystem / trigger Publisher Set |
| `src/render/gemini_render.py` | `render_image()` and `render_batch()` for Gemini 2.5 Flash Image |
| `scripts/ingest_pdf.py` | full CLI: PDF → PlanGraph → tape → HTML review |
| `scripts/revise_plan.py` | apply NL revision to a saved PlanGraph |
| `scripts/render_views.py` | render captured PNGs |

## Quickstart

```bash
# 1. Fill in your Gemini key.
cp .env.example .env
$EDITOR .env       # GEMINI_API_KEY=…

# 2. Install new deps.
pip install -r requirements.txt

# 3. Ingest a reference PDF (writes plan + tape + HTML review).
python scripts/ingest_pdf.py path/to/existing_conditions.pdf \
    --project "Southbend Western" --level "Ground"

# 4. Open the review.
open ingest_output/existing_conditions_review.html

# 5. (Optional) push to a running Archicad.
python scripts/ingest_pdf.py path/to/existing_conditions.pdf --apply

# 6. Apply a revision request.
python scripts/revise_plan.py ingest_output/existing_conditions_plan.json \
    --request "Remove wall between Reception and Office. Add 36-inch door to Treatment 1."

# 7. Capture model views (manual export to a folder OR Publisher Set), then render.
python scripts/render_views.py --capture-dir captures/
```

## Configuration

Everything tunable lives in `config/ingest.json`:

- `classifier.min_vector_paths_for_vector_page` — page is "vector" iff it has
  at least this many extracted vector paths. Below the threshold we route
  through Gemini Vision instead.
- `vector_parser.min_wall_length_in` — minimum centerline length to consider
  a line-pair a wall. Set higher if you get too many false-positive walls.
- `vector_parser.wall_pair_max_separation_in` — maximum spacing between the
  two edges of a wall pair. Set to your real-world wall thickness ceiling.
- `vision_parser.model` — switch to `gemini-2.5-flash` to cut costs.
- `render.default_style_prompt` — base prompt used for renders; override per
  call with `--style`.
- `build.wall_layer_existing|demo|new` — Archicad layer names for each
  renovation phase.

## Known limitations & honest expectations

- **Accuracy depends on the source PDF.** Clean vector exports from
  AutoCAD/Revit hit the target. Hand-drawn scans degrade — Gemini does its
  best but will mis-identify windows vs. doors on busy plans. **Always
  review `<stem>_review.html` before `--apply`.**
- **Scale inference is heuristic.** If a page lacks an explicit
  `1/4" = 1'-0"` annotation we fall back to the most common architectural
  scale with low confidence. The review HTML flags this in warnings.
- **Door/window placement on vector PDFs is not yet automatic** — the
  vector parser produces walls only; openings come in via the vision
  parser. Pass `--force vision` to get openings from a vector PDF too
  (slower, costs Gemini calls).
- **Live Archicad placement for doors/windows requires `ownerWallId`** —
  the builder maps placeholder IDs to real GUIDs returned by
  `API.CreateElements`, but the exact JSON command shape varies by
  Archicad version. The tape is always written so you can replay manually.
- **No UpCodes integration yet.** That stage is deferred until we have a
  confirmed access path (API tier or a structured-checklist fallback).

## Testing

```bash
pytest tests/test_ingest.py -v    # 14 offline tests, no Gemini calls
pytest tests/ -v                  # full suite (29 tests)
```

The ingest tests cover scale inference, wall-pairing geometry,
`PlanGraph` serialisation, and tape-format invariants. None of them
hit the network or require Archicad.
