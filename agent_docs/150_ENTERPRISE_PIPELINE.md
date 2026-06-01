# Enterprise Pipeline Architecture — Design Proposal

> **Status:** Draft v1. For review before any code moves.
> **Author:** Pipeline rearchitecture working group (Software Engineering
> team + Architectural Design team).
> **Last updated:** 2026-05-28
> **Decision required by:** Daniel Smith.

---

## Context-switch recap (10 bullets)

1. The current pipeline is a flat set of route variants (`vector`,
   `vision`, `hybrid`, `vector-hybrid`, `vector-truth`) selected by a
   `--force` flag. Stage boundaries are implicit.
2. Output is one big `PlanGraph` blob plus a separate scheduler step;
   the CSI division organization is bolted on after the fact.
3. The proposal: **named stages with explicit Pydantic contracts**,
   output **grouped by CSI division module** from the start, and
   **observability + testing** at every stage boundary.
4. Seven stages: **Acquire → Extract → Normalize → Classify →
   Assemble → Validate → Emit**.
5. Each stage has one responsibility, one input schema, one output
   schema, one failure mode story.
6. Geometry and AI calls live in separate stages so deterministic
   work is never mixed with probabilistic work in the same module.
7. CSI division modules under `src/divisions/` own division-specific
   knowledge (typical assemblies, schedules, layer names) so growing
   a new division is a new file, not a refactor.
8. Orchestrator runs stages with **telemetry**, **resumability**
   (per-stage cache), and **idempotency** (same input → same output).
9. Migration is incremental: build the new pipeline alongside the
   existing one; switch `--force` routes to call the new pipeline
   one at a time; deprecate old code only when nothing references it.
10. This is a design doc, not a contract. Review it, mark up the open
    questions in §13, and the working group will finalize before any
    code lands.

---

## 1. Executive summary

**What's changing:** The ingest pipeline becomes a 7-stage,
contract-based system. Output is organized by CSI MasterFormat
division. Every stage has a Pydantic input schema, a Pydantic output
schema, structured telemetry, and contract tests.

**What's not changing:** The PDF-in / schedule-out user contract
(`scripts/ingest_pdf.py`) stays. The CLI flags stay. The output
filenames stay. Internally, the implementation behind those flags is
replaced incrementally with a stage-based architecture.

**Why now:** The current pipeline has reached the size where
adding a new route or output format requires understanding the whole
system. Enterprise pipelines partition responsibility so a new
contributor can change one thing without breaking three others.

---

## 2. Problem statement

### What's wrong with the current architecture

1. **Implicit stage boundaries.** `vector_hybrid_ingest()` runs vector
   extraction, vision parsing, calibration, snap-to-walls, fixture
   import, and accuracy checking in one function. The function is the
   pipeline — no smaller unit to test, profile, or replace.
2. **Mixed concerns.** Pure-geometry math and AI calls live in the
   same module. A vector-only run still imports the vision provider.
3. **AI failure modes are silent.** When Claude hallucinates wall
   coordinates, the rest of the pipeline accepts them and ships a
   broken plan.
4. **No structured observability.** Logs go to stdout in free-form
   text. No machine-readable record of what stage did what, when,
   with which inputs.
5. **Re-runs are not idempotent.** Calibration drift between runs
   (Claude's `inches_per_norm` varies) means two identical inputs
   produce different outputs.
6. **No per-stage cache.** A trivial change in the validation step
   re-runs the expensive vision call.
7. **Division-by-division output is computed post-hoc.** The CSI
   organization in `src/decide/scheduler.py` discovers divisions
   from what was extracted. There's no canonical "Division 08
   processor" that knows what a door extraction should look like.
8. **Tests cover narrow slices.** 29 tests pass; they validate
   building blocks but not the end-to-end contract between stages.
9. **Growth pressure is on the wrong places.** Adding a new
   division (e.g., Division 21 Fire Suppression) requires editing
   the scheduler, the CSI config, and the exporter — three files in
   three modules.

### What "enterprise-grade" means here

- **Contract-driven stage boundaries.** Each stage's input/output is
  a versioned Pydantic schema. Stages don't share state through
  mutation.
- **Observable.** Every stage emits structured telemetry (start,
  finish, duration, input hash, output hash, errors).
- **Resumable.** A failed run can resume from the last completed
  stage by reading its cached output.
- **Idempotent.** Same input → same output, every time. AI
  responses get cached by input hash.
- **Testable at every boundary.** Stage 3 has contract tests on its
  inputs (what Stage 2 produces) and outputs (what Stage 4 expects).
- **Modular by CSI division.** Each division is a module that owns
  its assemblies, schedules, exporters. New divisions are new
  modules.
- **Honest about AI.** Probabilistic stages declare themselves as
  such; their outputs carry confidence scores; downstream code can
  branch on confidence.

---

## 3. Design principles

These principles drive every per-stage decision.

### 3.1 One responsibility per stage

A stage answers exactly one question:

| Stage | Question |
|---|---|
| Acquire | "Which PDF page are we processing, and how do we render it?" |
| Extract | "What primitives does this page contain?" |
| Normalize | "What's the clean geometry + the scale?" |
| Classify | "For each primitive, which AIA layer + CSI division?" |
| Assemble | "What buildable components do these primitives form?" |
| Validate | "Is the assembled model internally consistent + code-compliant?" |
| Emit | "What artifacts do we write for this run?" |

If a stage answers two questions, it splits.

### 3.2 Schemas are contracts

Every stage boundary is a Pydantic model with:
- An explicit `schema_version: str` field (e.g., "1.0").
- Required fields with types.
- Optional fields with defaults.
- A `meta` block carrying provenance (stage name, started, duration,
  inputs hash, outputs hash).

Schemas are versioned. Breaking changes bump the major version and
include a migration path.

### 3.3 Deterministic before probabilistic

Geometry math (Stages 2, 3, 5) is purely deterministic. AI calls
(Stage 4) are probabilistic and isolated to one stage. This means:

- A vector-only PDF can run Stages 2-5 + 7 without ever loading
  the vision provider.
- The probabilistic stage caches its outputs by input hash, so re-runs
  are deterministic from the consumer's point of view.
- Confidence scores propagate downstream so Stage 6 can flag
  low-confidence elements.

### 3.4 CSI division is a first-class organizing principle

Output is grouped by CSI division throughout. A wall doesn't get a
CSI division at the end (in the scheduler); it gets one at
classification (Stage 4) and stays in that division module for the
rest of the pipeline.

### 3.5 Idempotent + resumable

- **Idempotent:** Same input → same output. Achieved by caching
  AI calls by input hash; pure-deterministic stages are
  idempotent by construction.
- **Resumable:** Each stage writes its output to a cache directory
  keyed by input hash. A failed Stage 5 doesn't re-run Stage 4.
- **Bypass-able:** A user can manually edit a stage output and re-run
  from the next stage. Used for "fix the classification by hand and
  see what happens" workflows.

### 3.6 Observable by default

Every stage emits structured telemetry (JSON Lines) per run:

```jsonl
{"ts": "2026-05-28T19:01:23Z", "run_id": "abc123", "stage": "extract", "event": "start", "input_hash": "sha256:..."}
{"ts": "2026-05-28T19:01:25Z", "run_id": "abc123", "stage": "extract", "event": "progress", "msg": "1726 lines, 177 rects, 2325 curves"}
{"ts": "2026-05-28T19:01:25Z", "run_id": "abc123", "stage": "extract", "event": "finish", "duration_ms": 2103, "output_hash": "sha256:..."}
```

Default destination: `runs/<run_id>/telemetry.jsonl`. Optional sink:
stdout (current behaviour), file, both. Future: OpenTelemetry exporter.

### 3.7 Honest failure modes

Each stage declares:
- Its **inputs invariants** (what must be true for it to start).
- Its **outputs invariants** (what it guarantees on success).
- Its **failure modes** (named exceptions, what they mean).
- Its **degradation modes** (when it can produce partial output
  with a warning instead of failing).

---

## 4. Architecture overview

```
   ┌────────────────────────────────────────────────────────────────┐
   │                       Orchestrator                             │
   │  - Reads run config + arguments                                │
   │  - Walks stages 1-7 in order                                   │
   │  - Caches per-stage output keyed by input hash                 │
   │  - Emits structured telemetry                                  │
   │  - On stage failure: stops, preserves prior outputs            │
   └─────┬──────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 1: Acquire                                                │
   │  in: AcquireRequest                                             │
   │  out: AcquireResult (pdf_path, page_idx, page_size, png_bytes)  │
   │       runs/<rid>/01_acquire.json                                │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 2: Extract                                                │
   │  in:  AcquireResult                                             │
   │  out: ExtractResult (primitives, text_spans, stroke_histogram)  │
   │       runs/<rid>/02_extract.json + primitives.parquet           │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 3: Normalize                                              │
   │  in:  ExtractResult                                             │
   │  out: NormalizedGeometry (cleaned primitives + calibration)     │
   │       runs/<rid>/03_normalize.json                              │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 4: Classify       ← only AI stage                         │
   │  in:  NormalizedGeometry + ExtractResult                        │
   │  out: ClassifiedPrimitives (each with AIA layer + CSI div)      │
   │       runs/<rid>/04_classify.json                               │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 5: Assemble                                               │
   │  in:  ClassifiedPrimitives                                      │
   │  out: AssemblyResult (components grouped by CSI division)       │
   │       runs/<rid>/05_assemble.json                               │
   │                                                                 │
   │  Per-division processors live in src/divisions/                 │
   │   div_02_existing_conditions ─┐                                 │
   │   div_03_concrete             ├─→ each processor returns        │
   │   div_08_openings             │   list of Components            │
   │   div_09_finishes             │                                 │
   │   div_22_plumbing             │                                 │
   │   ...                         ┘                                 │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 6: Validate                                               │
   │  in:  AssemblyResult                                            │
   │  out: ValidationReport (passes / warnings / failures)           │
   │       runs/<rid>/06_validate.json                               │
   └─────┬───────────────────────────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ Stage 7: Emit                                                   │
   │  in:  AssemblyResult + ValidationReport                         │
   │  out: EmitResult (artifact paths + checksums)                   │
   │       runs/<rid>/07_emit.json                                   │
   │       + ingest_output/<stem>_*.svg / .csv / .json / .html       │
   └─────────────────────────────────────────────────────────────────┘
```

---

## 5. Stage specifications

Each stage section covers: responsibility, inputs schema, outputs
schema, activities, failure modes, telemetry events, contract tests.

### Stage 1: Acquire

**Responsibility:** Translate a PDF path + page hint into a
fully-rendered, classified page ready for extraction.

**Inputs (`AcquireRequest`):**
```python
class AcquireRequest(BaseModel):
    schema_version: str = "1.0"
    pdf_path: Path
    page_index: int | None = None       # None = auto-pick floor-plan page
    render_dpi: int = 200
    project_metadata: dict = Field(default_factory=dict)
```

**Outputs (`AcquireResult`):**
```python
class AcquireResult(BaseModel):
    schema_version: str = "1.0"
    pdf_path: Path
    page_index: int
    page_size_pt: tuple[float, float]
    render_dpi: int
    png_path: Path                       # rendered image lives here
    is_vector: bool                      # has parseable vector geometry
    has_text: bool                       # has extractable text (not outlined)
    classification_reason: str
    meta: StageMeta
```

**Activities:**
1. Open PDF with pdfplumber.
2. If `page_index is None`, classify each page and auto-pick the
   floor-plan page (most vector paths or most text).
3. Render the selected page to PNG at `render_dpi`.
4. Probe for text vs outlined-text-as-paths.

**Failure modes:**
- `PDFNotReadable` — pdfplumber can't open the file.
- `PageOutOfRange` — explicit `page_index` exceeds page count.
- `NoCandidatePage` — auto-pick can't find a plan-like page.

**Contract tests:**
- Multi-page PDFs auto-pick the right page.
- Outlined-text PDFs report `has_text=False`.
- Vector PDFs report `is_vector=True`.

---

### Stage 2: Extract

**Responsibility:** Pull every primitive from the PDF page,
losslessly, with stroke metadata.

**Inputs:** `AcquireResult`.

**Outputs (`ExtractResult`):**
```python
class Primitive(BaseModel):
    id: str                              # stable hash of geometry + width
    kind: Literal["line", "rect", "curve"]
    coords: list[tuple[float, float]]    # in PDF user space (pt)
    stroke_width_pt: float
    fill: str | None = None              # if applicable

class TextSpan(BaseModel):
    text: str
    bbox_pt: tuple[float, float, float, float]
    font: str
    size_pt: float

class ExtractResult(BaseModel):
    schema_version: str = "1.0"
    page_size_pt: tuple[float, float]
    primitives: list[Primitive]
    text_spans: list[TextSpan]
    stroke_histogram: dict[float, int]    # stroke_width -> count
    primitives_parquet_path: Path | None  # large extracts get a parquet sidecar
    meta: StageMeta
```

**Activities:**
1. Walk `page.lines`, `page.rects`, `page.curves`, `page.chars`.
2. Assign a stable `id` to each primitive (sha1 of geometry + width).
3. Build a stroke-width histogram so Stage 3 can pick thresholds
   from data, not from a hard-coded config.
4. If primitive count > 10K, persist the array as Parquet alongside
   the JSON (which only carries the histogram + counts).

**Failure modes:**
- `ExtractMalformedPDF` — pdfplumber throws on a specific page.

**Contract tests:**
- Idempotency: same PDF → same primitive IDs (sha1 is deterministic).
- Histogram: distribution sums to total primitive count.

---

### Stage 3: Normalize

**Responsibility:** Convert raw primitives into clean geometry with
a real-world scale.

**Inputs:** `ExtractResult`.

**Outputs (`NormalizedGeometry`):**
```python
class CalibrationResult(BaseModel):
    inches_per_norm: float
    source: Literal["scale_text", "dim_callout", "default", "manual_override"]
    dim_text: str = ""
    confidence: float                    # 0..1

class NormalizedGeometry(BaseModel):
    schema_version: str = "1.0"
    primitives_by_stroke_class: dict[str, list[Primitive]]
    # "wall_weight" / "secondary" / "annotation" / "patterning"

    calibration: CalibrationResult
    page_size_pt: tuple[float, float]
    page_size_in: tuple[float, float]    # = page_size_pt / 72
    drawing_area_norm_bbox: list[float] | None  # may be populated by Classify later
    meta: StageMeta
```

**Activities:**
1. Apply dedupe + endpoint snap + collinear merge (see
   `src/ingest/geometry/snap.py`).
2. Bucket primitives by stroke class from the histogram (k-means
   or fixed cutoff per project).
3. Infer scale calibration from text spans (look for "1/4\" = 1'-0\"")
   or fall back to default with low confidence.

**Failure modes:**
- `CalibrationFailed` — no calibration possible; fall back to
  default with `confidence=0.0` and a warning.

**Contract tests:**
- Dedupe removes exact-duplicate lines.
- Snap collapses endpoints within tolerance.
- Calibration extracts the right number from a known dimension callout.

---

### Stage 4: Classify

**Responsibility:** For every primitive, assign AIA layer + CSI
division + sub-category. **This is the only AI stage.**

**Inputs:** `NormalizedGeometry` + `ExtractResult.text_spans`.

**Outputs (`ClassifiedPrimitives`):**
```python
class Classification(BaseModel):
    primitive_id: str
    aia_layer: str                       # e.g. "A-WALL-EXST"
    csi_division: str                    # e.g. "02"
    subcategory: str                     # e.g. "Wall — Existing"
    confidence: float                    # 0..1
    source: Literal["stroke_weight", "geometric_pattern", "ai_vision", "text_label"]

class ClassifiedPrimitives(BaseModel):
    schema_version: str = "1.0"
    classifications: list[Classification]
    semantic_labels: dict[str, str]      # primitive_id -> room name / fixture kind
    drawing_area_norm_bbox: list[float] | None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_cache_hit: bool = False
    meta: StageMeta
```

**Activities:**
1. **Deterministic pass:** Stroke-weight-based classification (Wall ↔
   heavy stroke, Door ↔ medium, etc.). High confidence.
2. **Geometric-pattern pass:** Detect door arcs (curve + line in
   right configuration), wall pairs (parallel close-spaced), grid
   lines (intersecting at 90°). Medium-high confidence.
3. **AI semantic pass:** For each enclosed region (or each
   medium-confidence primitive), ask the vision provider for a
   semantic label. Output: room names, fixture kinds.
4. **Cache hit check:** Hash the inputs to the AI call; if a cached
   response exists, reuse it and set `ai_cache_hit=True`.

**Failure modes:**
- `AIProviderUnavailable` — all configured providers failed.
  Falls back to deterministic-only classification with a warning;
  semantic labels are blank.

**Contract tests:**
- Stroke-weight classification on known PDFs.
- Cache hit on identical inputs.
- AI fallback when provider unavailable.

---

### Stage 5: Assemble

**Responsibility:** Group classified primitives into buildable
Components, organized by CSI division.

**Inputs:** `ClassifiedPrimitives`.

**Outputs (`AssemblyResult`):**
```python
class AssemblyResult(BaseModel):
    schema_version: str = "1.0"
    components_by_division: dict[str, list[Component]]
    # "02" -> [existing walls...]
    # "08" -> [doors, windows, ...]
    # "09" -> [new walls, floor finishes, ceilings, ...]
    # ...

    orphan_primitives: list[Primitive]   # didn't fit any component
    coverage: float                      # primitives used / total
    meta: StageMeta
```

**Activities:**
1. For each CSI division processor in `src/divisions/`, call its
   `assemble(classified) -> list[Component]` method.
2. Each processor knows its division's typical assemblies (e.g.
   `div_09` knows "interior stud wall = parallel line pair").
3. Track unconsumed primitives as orphans.

**Per-division processor pattern:**
```python
# src/divisions/div_08_openings/processor.py
class Div08OpeningsProcessor(DivisionProcessor):
    division_code = "08"
    division_name = "Openings"
    aia_layers = ["A-DOOR", "A-DOOR-IDEN", "A-GLAZ", "A-GLAZ-IDEN"]

    def assemble(
        self, classified: ClassifiedPrimitives,
    ) -> list[Component]:
        doors = self._assemble_doors(classified)
        windows = self._assemble_windows(classified)
        return doors + windows
```

**Failure modes:**
- `LowCoverage` — coverage < threshold. Warning, not failure;
  surfaces in Stage 6.

**Contract tests:**
- Per-division processors are independently testable.
- Coverage on known PDFs ≥ threshold.

---

### Stage 6: Validate

**Responsibility:** Check the assembled model for internal
consistency and external standards compliance.

**Inputs:** `AssemblyResult`.

**Outputs (`ValidationReport`):**
```python
class ValidationCheck(BaseModel):
    rule_id: str
    severity: Literal["info", "warning", "failure"]
    message: str
    component_ids: list[str]             # affected components

class ValidationReport(BaseModel):
    schema_version: str = "1.0"
    checks: list[ValidationCheck]
    summary: dict[str, int]              # severity -> count
    overall_status: Literal["pass", "warn", "fail"]
    blocks_emit: bool
    meta: StageMeta
```

**Validation rules** (each lives in `src/pipeline/validators/`):

1. **Geometry consistency** — dim callouts match measured geometry
   (existing accuracy_checker).
2. **Component completeness** — every door has a host wall; every
   room has a polygon.
3. **Cross-references** — every wall referenced by a door exists.
4. **Code minimums** — egress widths ≥ 32" clear; ADA clearances.
5. **Drafting standards** — every component has its AIA layer +
   CSI division populated.
6. **Schedule completeness** — every Wall has thickness/height/status;
   every Door has type/width/height/leaf material.

**Failure modes:**
- Failures with `blocks_emit=True` halt the pipeline before Stage 7.
- Warnings continue; user sees them in the review HTML.

**Contract tests:**
- Each rule tested with passing + failing cases.
- Overall status correctly aggregates from individual rule results.

---

### Stage 7: Emit

**Responsibility:** Generate every output artifact for the run.

**Inputs:** `AssemblyResult` + `ValidationReport`.

**Outputs (`EmitResult`):**
```python
class Artifact(BaseModel):
    path: Path
    kind: Literal["schedule_csv", "schedule_json", "svg_lossless",
                  "svg_layered", "svg_components", "review_html",
                  "archicad_tape", "plan_json"]
    sha256: str
    size_bytes: int

class EmitResult(BaseModel):
    schema_version: str = "1.0"
    artifacts: list[Artifact]
    output_dir: Path
    meta: StageMeta
```

**Activities:**
1. For each CSI division with components, emit:
   - Schedule CSV (one per division).
   - JSON sidecar with full component properties.
2. Generate three SVG outputs (lossless, layered, components).
3. Generate review HTML with the validation report inline.
4. Generate Archicad command tape (existing logic).
5. Compute sha256 of each artifact for reproducibility tracking.

**Failure modes:**
- `WriteFailed` — disk full / permission denied / path not writable.

**Contract tests:**
- Every artifact written; every kind covered.
- Artifact sha256 stable across re-runs with same input.

---

## 6. CSI division modules

The `src/divisions/` tree organizes division-specific logic so a new
division is a new module, not a refactor.

```
src/divisions/
├── __init__.py
├── base.py                          DivisionProcessor abstract base
├── registry.py                      Auto-discovers processors
│
├── div_02_existing_conditions/
│   ├── __init__.py
│   ├── processor.py                 assemble() for walls (existing, demo)
│   ├── schedules.py                 demo schedule format
│   └── README.md                    what this division covers
│
├── div_03_concrete/
│   ├── processor.py                 slabs, columns, foundations
│   └── ...
│
├── div_05_metals/                   structural steel, deck, columns
├── div_06_wood_plastics/            casework, millwork, stairs
├── div_07_thermal_moisture/         roofing, insulation, sealants
├── div_08_openings/                 doors, windows, hardware
├── div_09_finishes/                 new walls, finishes, ceilings
├── div_11_equipment/                fixed equipment
├── div_22_plumbing/                 fixtures
├── div_23_hvac/                     equipment, ducts
└── div_26_electrical/               panels, fixtures
```

### Base contract for a division processor

```python
# src/divisions/base.py
class DivisionProcessor(ABC):
    division_code: str           # "02", "08", "09", etc.
    division_name: str           # "Existing Conditions", "Openings", ...
    aia_layers: list[str]        # AIA layers this processor handles
    typical_sheets: list[str]    # sheets these components appear on

    @abstractmethod
    def assemble(
        self, classified: ClassifiedPrimitives,
    ) -> list[Component]:
        """Take classified primitives, return buildable components."""

    @abstractmethod
    def schedule_columns(self) -> list[str]:
        """The columns in this division's schedule CSV."""

    @abstractmethod
    def row_for_component(self, c: Component) -> dict:
        """Render a component as a schedule row."""
```

### Registry pattern

```python
# src/divisions/registry.py
def all_processors() -> list[DivisionProcessor]:
    """Discover every DivisionProcessor subclass under src/divisions/."""
    # importlib walks src/divisions/*/processor.py
    # returns instantiated processors
```

Stage 5 calls `all_processors()` and routes each one its slice of the
classified primitives.

### Growing a new division

To add Division 21 (Fire Suppression):

1. `mkdir src/divisions/div_21_fire_suppression/`
2. Create `processor.py` with a `Div21FireSuppressionProcessor`.
3. Implement `assemble()`, `schedule_columns()`, `row_for_component()`.
4. Add a `README.md` documenting what this division processes.
5. Add a contract test under `tests/divisions/test_div_21.py`.

No other files change. Stage 5 picks the new processor up via the
registry.

---

## 7. Data flow + schemas

### Single Component model — shared across divisions

The Component schemas already shipped (`src/components/schemas.py`)
become the canonical types. Each division processor produces
`Component` subclasses (`WallComponent`, `DoorComponent`, etc.).

### Run artifacts on disk

```
runs/<run_id>/
├── manifest.json                  run metadata, args, environment
├── telemetry.jsonl                structured event log
├── 01_acquire.json                stage outputs (per stage)
├── 02_extract.json                + primitives.parquet if large
├── 03_normalize.json
├── 04_classify.json
├── 05_assemble.json
├── 06_validate.json
└── 07_emit.json                   lists artifacts + their sha256
```

### User-facing outputs (existing)

```
ingest_output/<stem>_*.svg
ingest_output/<stem>_*.csv
ingest_output/<stem>_*.html
ingest_output/<stem>_*.json
```

These stay where they are. The `runs/` tree is internal observability.

### Schema versioning

Every Pydantic model has `schema_version: str = "1.0"`. On a breaking
change:

1. Bump major (e.g. "2.0").
2. Add a migration function under `src/pipeline/migrations/`.
3. The orchestrator's cache loader checks version on load and
   migrates if older.

---

## 8. Error handling + observability

### Structured exceptions

```python
class PipelineError(Exception):
    stage: str
    code: str                # e.g. "EXTRACT_MALFORMED_PDF"
    remediation: str         # what the user should do

class PDFNotReadable(PipelineError):
    stage = "acquire"
    code = "ACQUIRE_PDF_NOT_READABLE"
    remediation = "Verify the PDF opens in Preview/Acrobat..."
```

### Telemetry schema

Every event is a JSON object:

```python
class TelemetryEvent(BaseModel):
    ts: datetime
    run_id: str
    stage: str
    event: Literal["start", "progress", "finish", "error"]
    msg: str = ""
    duration_ms: int | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    error_code: str | None = None
```

Default sink: `runs/<run_id>/telemetry.jsonl`. Optional sinks:
stdout, file, OpenTelemetry.

### Run manifest

```json
{
  "run_id": "abc123",
  "started": "2026-05-28T19:01:23Z",
  "finished": "2026-05-28T19:02:45Z",
  "duration_ms": 82103,
  "pipeline_version": "2.0.0",
  "stages_completed": ["acquire", "extract", "normalize", "classify",
                       "assemble", "validate", "emit"],
  "args": { "pdf_path": "...", "page_index": null, ... },
  "environment": { "python": "3.11.15", "git_sha": "8d8fa57" },
  "outputs": { "artifacts_count": 12, "total_bytes": 1843217 }
}
```

The manifest is the "what happened" answer for any past run.

### Caching

Per-stage cache directory keyed by SHA256 of stage inputs:

```
.pipeline_cache/
├── stage_02_extract/
│   ├── <input_sha256>.json
│   └── <input_sha256>.parquet
├── stage_04_classify/
│   └── <input_sha256>.json     ← AI cache hit lives here
└── ...
```

A cache hit short-circuits the stage with the cached output. Cache
TTL: indefinite for deterministic stages; configurable for AI stage
(default: 30 days).

---

## 9. Testing strategy

### Per-stage unit tests

Each stage has tests for:
- Happy path with known input.
- Each declared failure mode.
- Edge cases (empty input, single primitive, max load).
- Idempotency (same input → same output).

### Contract tests at boundaries

For each pair of adjacent stages:
- Tests that Stage N's output is valid as Stage N+1's input.
- Includes schema-version compatibility.

### Golden tests on known PDFs

A small set of reference PDFs in `tests/fixtures/`:
- `oly_cats.pdf` — vector clinic plan.
- `southbend_matterport.pdf` — Matterport scan (raster-ish).
- `simple_rectangle.pdf` — minimal known geometry.

Each fixture has expected outputs checked into the repo. Pipeline
changes that alter outputs require updating the fixture, with a
PR explanation of why.

### Online tests

AI provider calls are marked `@pytest.mark.online`. CI doesn't
run them. Local devs run them with `pytest -m online` + their own
keys.

### CI mapping

CI runs (in current workflow):
- `lint` (ruff)
- `test` (pytest, offline only)
- `validate-configs` (JSON parse)

Future CI additions:
- `contract-test` — runs the cross-stage contract tests
- `golden-test` — runs the known-PDF golden tests (no AI)

---

## 10. CSI division coverage matrix

Which divisions are processed at launch vs deferred:

| Division | Name | Status at launch |
|---|---|---|
| 02 | Existing Conditions | **In** — existing walls, demo |
| 03 | Concrete | Stub processor (foundations from slab vec) |
| 05 | Metals | Stub processor (steel columns from vec) |
| 06 | Wood, Plastics, Composites | **In** — casework, millwork, stairs |
| 07 | Thermal + Moisture | Deferred (rare in interior renovation) |
| 08 | Openings | **In** — doors, windows |
| 09 | Finishes | **In** — new walls, floor finishes, ceilings |
| 11 | Equipment | **In** — fixed equipment |
| 22 | Plumbing | **In** — plumbing fixtures (arch view) |
| 23 | HVAC | Stub processor (RTUs from roof plan if available) |
| 26 | Electrical | Stub processor (lighting from RCP if available) |

"Stub processor" = present in the registry, returns empty list at
launch. The division module exists so adding real assembly later is
a single-file change.

---

## 11. Migration plan

### Phase A: Foundation (zero behaviour change)

1. Create `src/pipeline/` skeleton with stage interfaces +
   Pydantic schemas. Empty implementations that pass-through.
2. Create `src/divisions/` skeleton with the registry pattern.
3. Add contract tests at every stage boundary.
4. CI runs the new tests alongside the old ones.

No user-visible change. Old `--force vector-hybrid` still works.

### Phase B: Stage-by-stage migration

For each existing route (`vector`, `vision`, `hybrid`, `vector-hybrid`,
`vector-truth`):

1. Reimplement its logic as the appropriate stages.
2. Add a feature flag `--use-new-pipeline` that switches the route
   to the new implementation.
3. Run side-by-side with the old implementation; diff the outputs.
4. When outputs match (or diffs are intentional improvements),
   make `--use-new-pipeline` the default and rename the old as
   `--use-legacy-pipeline`.

### Phase C: Cleanup

1. Once all routes use the new pipeline, deprecate `--use-legacy-pipeline`.
2. Remove the old modules.
3. Update `agent_docs/100_INGEST_PIPELINE.md` to reflect new state.
4. Bump version to 2.0.0.

### Order of route migration

1. `vector-truth` (simplest, no AI) — first to migrate.
2. `vision` (AI-only, isolated to Stage 4) — second.
3. `vector-hybrid` (current default) — third.
4. `hybrid`, `vector` — deprecated; consolidate into `vector-hybrid`.

### Rollback strategy

Each migrated route keeps the legacy path until 2 releases after its
new path is the default. The `--use-legacy-pipeline` flag is the
escape hatch.

---

## 12. Acceptance criteria

The rearchitecture is done when:

1. ✅ Every CLI command produces the same outputs as before (or
   better).
2. ✅ `runs/<run_id>/` directory carries telemetry + per-stage
   artifacts for every run.
3. ✅ A failed run can resume from the last completed stage.
4. ✅ Same input + same code + same config → same output sha256.
5. ✅ AI calls are cached by input hash; second run with same PDF
   doesn't hit the AI again.
6. ✅ Each CSI division has its own processor; new divisions can be
   added as a single new module.
7. ✅ Validation report flags every documented quality issue.
8. ✅ Contract tests cover every stage boundary.
9. ✅ Golden tests pass on the reference PDFs.
10. ✅ `agent_docs/100_INGEST_PIPELINE.md` reflects the new architecture.

---

## 13. Decisions (resolved 2026-06-01)

All 10 open questions were walked with the owner on 2026-06-01. Every
decision matched the original recommendation, captured below. Sections
13.1–13.10 retain the rationale for future readers.

| # | Topic | Decision |
|---|---|---|
| 13.1 | Cache eviction | TTL 30d for AI stage; deterministic stages never expire |
| 13.2 | Parallelism | Sequential at launch; `--parallel` feature flag once profiling justifies it |
| 13.3 | Cache location | Repo root `./.pipeline_cache/`, gitignored |
| 13.4 | Telemetry | File only: `runs/<run_id>/telemetry.jsonl` |
| 13.5 | Validation blocking | Per-rule severity (each rule declares blocking or non-blocking) |
| 13.6 | Schema versioning | Semver — minor for additive, major for breaking |
| 13.7 | Low-confidence handling | Assemble anyway; validator flags it |
| 13.8 | Launch division coverage | Full processors: 02, 06, 08, 09, 11, 22. Stubs: 03, 05, 07, 23, 26 |
| 13.9 | Backward compatibility | Old `--force <route>` flags work for 2 releases past default-flip with deprecation warning |
| 13.10 | AI cost cap | Soft $0.50 / hard $5 per run, configurable, tracked in run manifest |

These resolutions unblock Phase A. Phase A may begin.

---

### 13.1 Cache eviction policy

When does the per-stage cache get purged?

- **Option A** — never (manual purge).
- **Option B** — TTL (e.g., 30 days for AI, indefinite for
  deterministic).
- **Option C** — LRU with disk-space budget.

**Recommendation:** Option B for AI stage, never for deterministic
stages. Provides correctness + cheap re-runs.

### 13.2 Per-stage parallelism

Should stages run in parallel where independent?

- Extract + Normalize: must be sequential.
- Classify per-region could parallelize.
- Per-division processors in Stage 5 are independent and parallel-safe.

**Recommendation:** Sequential at launch (simpler). Add parallelism
behind a feature flag once profiling shows it matters.

### 13.3 Cache directory location

Where does `.pipeline_cache/` live?

- **Option A** — repo root (in `.gitignore`).
- **Option B** — `~/.cache/api-service-integration/`.
- **Option C** — `$XDG_CACHE_HOME/api-service-integration/`.

**Recommendation:** Repo root, gitignored. Easy to inspect /
nuke; per-project isolated.

### 13.4 Telemetry destination

Default destination for the JSONL telemetry stream?

- **Option A** — file only (`runs/<rid>/telemetry.jsonl`).
- **Option B** — file + stdout.
- **Option C** — OpenTelemetry collector.

**Recommendation:** A at launch. Add OpenTelemetry behind a flag
when we run this for someone else's project.

### 13.5 Validation strictness

Should validation failures block emit?

- **Option A** — always (safer, but blocks legitimate "show me the
  partial output" workflows).
- **Option B** — never (user always sees output; flags via report).
- **Option C** — configurable per-rule (each rule declares blocking
  or non-blocking).

**Recommendation:** C. Severity is a property of the rule, not a
global config.

### 13.6 Schema versioning approach

How strict should we be about schema versions?

- **Option A** — every minor change bumps minor; breaking bumps major.
- **Option B** — only breaking changes bump version.
- **Option C** — date-based (`2026.05.28`).

**Recommendation:** B. Semver, minor for backwards-compatible
additions only.

### 13.7 Confidence-score handling downstream

When Stage 4's classification has low confidence, what should
Stage 5 do?

- **Option A** — still assemble; the validator catches it.
- **Option B** — skip low-confidence classifications; orphan them.
- **Option C** — emit two output sets: high-confidence and
  low-confidence; user picks.

**Recommendation:** A. Keep the pipeline simple; let validation
handle quality.

### 13.8 Division coverage launch scope

Which divisions get full processors at launch vs deferred?

**Recommendation:** See §10 matrix. Cover 02, 06, 08, 09, 11, 22 at
launch; stubs for the rest.

### 13.9 Backward compatibility

How long do we maintain the old `--force vector-hybrid` etc. flags?

**Recommendation:** 2 releases past the new pipeline becoming the
default. Deprecation warning, then removal.

### 13.10 Cost cap on AI stage

Should we cap per-run cost on the AI stage?

**Recommendation:** Yes. Default soft cap = $0.50 per run; hard cap
= $5. Configurable. Tracked in the run manifest.

---

## 14. Appendix A: target file/folder structure

```
src/
├── pipeline/                       NEW — stage orchestration + interfaces
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage_01_acquire.py
│   │   ├── stage_02_extract.py
│   │   ├── stage_03_normalize.py
│   │   ├── stage_04_classify.py
│   │   ├── stage_05_assemble.py
│   │   ├── stage_06_validate.py
│   │   └── stage_07_emit.py
│   ├── schemas/                    Pydantic models per stage boundary
│   │   ├── acquire.py
│   │   ├── extract.py
│   │   ├── normalize.py
│   │   ├── classify.py
│   │   ├── assemble.py
│   │   ├── validate.py
│   │   └── emit.py
│   ├── telemetry.py                structured event emitter
│   ├── cache.py                    per-stage cache wrapper
│   ├── validators/                 individual validation rules
│   │   ├── geometry.py
│   │   ├── cross_refs.py
│   │   ├── code_compliance.py
│   │   └── completeness.py
│   ├── migrations/                 schema migrations across versions
│   └── exceptions.py               structured pipeline exceptions
│
├── divisions/                      NEW — per-CSI-division logic
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── div_02_existing_conditions/
│   ├── div_03_concrete/
│   ├── div_05_metals/
│   ├── div_06_wood_plastics/
│   ├── div_07_thermal_moisture/
│   ├── div_08_openings/
│   ├── div_09_finishes/
│   ├── div_11_equipment/
│   ├── div_22_plumbing/
│   ├── div_23_hvac/
│   └── div_26_electrical/
│
├── ingest/                         EXISTING — to be migrated then retired
├── decide/                         EXISTING — scheduler logic moves into
│                                   divisions/; layer/CSI mapping moves to
│                                   pipeline/schemas/
├── apply/                          EXISTING — SVG exporters become Stage 7
│                                   sinks
├── components/                     EXISTING — schemas stay; builder logic
│                                   moves into divisions/
├── knowledge/                      EXISTING — unchanged; consulted by
│                                   Classify + Validate
└── build/                          EXISTING — Archicad tape becomes a
                                    Stage 7 sink

tests/
├── unit/                           per-module unit tests (existing)
├── stages/                         NEW — per-stage tests
│   ├── test_stage_01_acquire.py
│   ├── test_stage_02_extract.py
│   ├── ...
├── contract/                       NEW — boundary contract tests
│   ├── test_acquire_to_extract.py
│   ├── test_extract_to_normalize.py
│   ├── ...
├── divisions/                      NEW — per-division processor tests
│   ├── test_div_02.py
│   ├── ...
├── golden/                         NEW — reference-PDF golden tests
│   └── test_oly_cats_baseline.py
└── fixtures/                       NEW — reference PDFs + expected outputs
    ├── pdfs/
    │   ├── simple_rectangle.pdf
    │   ├── oly_cats.pdf
    │   └── southbend_matterport.pdf
    └── expected/
        ├── simple_rectangle_assemble.json
        ├── ...

runs/                               NEW — per-run telemetry + cached outputs
└── .gitkeep                        directory tracked, contents gitignored

.pipeline_cache/                    NEW — per-stage input-hashed cache
└── .gitkeep                        gitignored
```

---

## 15. Appendix B: example stage code skeleton

This is what a stage looks like under the new design:

```python
# src/pipeline/stages/stage_03_normalize.py

from ..schemas.extract import ExtractResult
from ..schemas.normalize import NormalizedGeometry, CalibrationResult
from ..telemetry import emit
from ..cache import staged_cache
from ..exceptions import PipelineError


class NormalizeError(PipelineError):
    stage = "normalize"


@staged_cache
def run(req: ExtractResult, *, run_id: str) -> NormalizedGeometry:
    """Stage 3: dedupe + snap + merge + calibrate."""
    emit(run_id, "normalize", "start",
         input_hash=req.meta.output_hash)

    # ── Dedupe + snap + merge ─────────────────────────────────────
    cleaned = clean_pipeline(req.primitives, snap_tol=0.001)
    emit(run_id, "normalize", "progress",
         msg=f"clean {len(req.primitives)} -> {len(cleaned)}")

    # ── Stroke classification ────────────────────────────────────
    by_class = classify_by_stroke(cleaned, histogram=req.stroke_histogram)

    # ── Calibration ──────────────────────────────────────────────
    calibration = calibrate(req.text_spans, req.page_size_pt)
    if calibration.confidence < 0.5:
        emit(run_id, "normalize", "progress",
             msg=f"low-confidence calibration ({calibration.confidence:.2f})")

    out = NormalizedGeometry(
        primitives_by_stroke_class=by_class,
        calibration=calibration,
        page_size_pt=req.page_size_pt,
        page_size_in=(req.page_size_pt[0] / 72, req.page_size_pt[1] / 72),
        meta=StageMeta.finished("normalize", input_hash=req.meta.output_hash),
    )

    emit(run_id, "normalize", "finish",
         output_hash=out.meta.output_hash,
         duration_ms=out.meta.duration_ms)
    return out
```

The shape is:
- Pure function: input model → output model.
- `@staged_cache` wraps caching transparently.
- `emit(...)` emits structured telemetry.
- Custom exception for stage-local errors.

---

## 16. Provenance + sign-off

**Authoring team consultations:**

- **Staff Engineer:** architecture, stage boundaries, schema design,
  observability, migration plan, acceptance criteria.
- **DBA:** schema versioning approach, cache directory layout, run
  manifest format, parquet sidecar for large extracts.
- **Backend Engineer:** stage orchestrator pattern, exception
  hierarchy, retry / fallback behavior, telemetry schema, AI cost cap.
- **Frontend Engineer:** validation report structure (so it can drive
  the review HTML), artifact paths consistent with current outputs.
- **QA Specialist:** contract tests, golden tests, fixture PDFs,
  CI mapping, rollback strategy.
- **Principal Architect:** CSI division coverage matrix, division
  selection criteria, what content each division module needs.
- **BIM Engineer:** component model fits Revit/Archicad import,
  AIA layer assignment lives in Stage 4 not buried in Stage 5.
- **Architectural Designer:** schedule columns per division match
  CD-set conventions.
- **Sustainability Specialist:** energy / IAQ data flows into the
  validation stage as future work; not in launch scope.

**Open questions** (§13) require user decision before any code lands.

**Once approved**, the next deliverables are:

1. Phase A foundation PR (skeleton + schemas + registry + tests).
2. Phase B route migrations (one PR per route).
3. Phase C cleanup (deprecation + removal of legacy).

No code starts before §13 has check-marks.
