# Layout Annotation Automation for Archicad 29

Automatically generate and maintain **layout sheet notes** (demolition notes, new-work notes, code notes, scope notes, etc.) for every sheet in an Archicad 29 project — driven by the **model**, **renovation phases**, and **configurable rules**.

**For architects and interior designers**: If you work on renovation projects and spend time writing and updating sheet notes based on what's being demolished, built new, or retained — this tool does that automatically by reading your Archicad model.

---

## Quickstart (local, no Archicad needed)

```bash
# 1. Clone and install
git clone <repo-url> && cd api-service-integration
pip install -r requirements.txt

# 2. Set up secrets (only needed for ingest/render with Gemini)
cp .env.example .env
$EDITOR .env       # GEMINI_API_KEY=...

# 3. Run with mock data (no Archicad needed)
python scripts/quick_demo.py --mock

# 4. Ingest a reference PDF into a PlanGraph + Archicad tape
python scripts/ingest_pdf.py path/to/existing_conditions.pdf

# 5. Run tests
pytest tests/ -v
```

Outputs:
- `output/SheetNotes.json` — sheet-notes pipeline (existing).
- `ingest_output/<stem>_plan.json` — structured PlanGraph from a PDF.
- `ingest_output/<stem>_tape.json` — Archicad command tape.
- `ingest_output/<stem>_review.html` — visual review of detected walls.

See [agent_docs/100_INGEST_PIPELINE.md](agent_docs/100_INGEST_PIPELINE.md)
for the PDF → Archicad → Gemini-render flow.

---

## Live Archicad run instructions

### Prerequisites

1. **Archicad 29** running with a project open.
2. **JSON API enabled**:
   - macOS: `Archicad → Settings → Work Environment → Experimental` → enable Python/JSON API on port `19723`.
   - Windows: `Options → Work Environment → Experimental` → enable Python/JSON API on port `19723`.
3. Restart Archicad if prompted.

### Run

```bash
# Step 1: Verify connection
python scripts/discover_commands.py --port 19723

# Step 2: Preview (no changes written)
python scripts/run_annotation.py --port 19723 --dry-run

# Step 3: Export JSON files
python scripts/run_annotation.py --port 19723 --apply json

# Step 4: (Optional) Write notes into Archicad custom properties
python scripts/run_annotation.py --port 19723 --apply property
```

### Smoke test

After Step 3, verify `output/SheetNotes.json` exists and contains sheets with `element_driven_notes` entries. After Step 4, open Archicad's Property Manager and check that `LayoutAnnotation > SheetNotesText` is populated on your layouts.

> See [agent_docs/30_ARCHICAD_INTEGRATION.md](agent_docs/30_ARCHICAD_INTEGRATION.md) for the full connection guide, execution modes, and C++ Add-On setup.

---

## How it works

```
   EXTRACT  →  DECIDE  →  APPLY
   (read AC)   (rules)    (write back / export)
```

1. **Extract**: Connects to Archicad, reads all elements (with renovation status, layers, properties) and all layouts from the Layout Book.
2. **Decide**: Evaluates configurable rules against each layout's element data. Produces per-sheet notes (demolition notes, new-work notes, plumbing coordination, etc.).
3. **Apply**: Either exports JSON files to `output/` (safe) or writes note text into a custom Archicad property on each Layout element.

### Three-layer design

| Layer | Directory | Purpose |
|---|---|---|
| **Extract** | `src/extract/` | Connect to Archicad, read elements, properties, layouts, renovation status |
| **Decide** | `src/decide/` | Evaluate rules, analyse phases, assemble note text (offline — no AC needed) |
| **Apply** | `src/apply/` | Export JSON, write custom properties, place text (C++ fallback) |

### Two approaches for displaying notes on sheets

| Approach | When to use |
|---|---|
| **A) Property-driven** (recommended) | Write notes to a custom property → GDL title-block object reads and renders them. Python-only. |
| **B) Hybrid (Python + C++)** | When you need to place 2D text elements directly on layouts. Requires the C++ Add-On. |

---

## Repo structure

```
api-service-integration/
├── README.md                    ← You are here
├── architecture.md              # Full design doc with diagrams
├── requirements.txt             # archicad, pydantic, pytest, rich
│
├── config/
│   ├── phases.json              # Renovation phase definitions (Existing, Demolition, New)
│   ├── rules.json               # Annotation rules (condition → note template)
│   ├── note_templates.json      # Boilerplate note text per section
│   ├── sheet_conventions.json   # Sheet prefix → discipline mapping (reference)
│   └── manual_overrides.json    # (optional) Per-sheet scope/manual notes
│
├── src/
│   ├── connection.py            # ArchicadConnection wrapper (single AC contact point)
│   ├── discovery.py             # Enumerate all JSON commands/types
│   ├── models/
│   │   └── data_model.py        # Pydantic models: ACElement, ACLayout, SheetNotes, etc.
│   ├── extract/
│   │   ├── elements.py          # Read elements (GetAllElements, enrich with properties)
│   │   ├── layouts.py           # Read navigator/LayoutBook (GetNavigatorItemTree)
│   │   ├── properties.py        # Resolve property names → IDs, read/write values
│   │   └── renovation.py        # Map renovation status int → Phase enum
│   ├── decide/
│   │   ├── phase_analyzer.py    # Count elements per phase per layout → LayoutPhaseReport
│   │   ├── rules_engine.py      # Evaluate rules against phase reports → NoteEntry list
│   │   └── note_builder.py      # Assemble global + rule + manual notes → SheetNotes
│   └── apply/
│       ├── json_exporter.py     # Export SheetNotes.json, per-sheet JSON, flat text
│       ├── property_writer.py   # Write notes to AC custom property on layouts
│       └── text_placer.py       # (stub) Direct 2D text placement (needs C++ Add-On)
│
├── scripts/
│   ├── run_annotation.py        # Full pipeline: Extract → Decide → Apply
│   ├── quick_demo.py            # Minimal working example (supports --mock)
│   └── discover_commands.py     # Print every available AC JSON command
│
├── tests/
│   ├── test_rules_engine.py     # 6 tests: rule evaluation correctness
│   └── test_note_builder.py     # 9 tests: note building + sheet ID parsing
│
├── output/                      # Generated artefacts (SheetNotes.json, per-sheet/, flat_text/)
│
├── addons/
│   └── layout_annotator_cpp/    # Optional C++ Add-On skeleton for direct text placement
│
└── agent_docs/                  # LLM agent documentation (context-switch friendly)
    ├── 00_START_HERE.md
    ├── 10_ARCHITECTURE.md
    ├── 20_WORKFLOWS.md
    ├── 30_ARCHICAD_INTEGRATION.md
    ├── 40_CODE_TO_ARCHICAD_MAP.md
    ├── 50_CONFIG_AND_SECRETS.md
    ├── 60_TROUBLESHOOTING.md
    ├── 70_TESTING.md
    ├── 80_GLOSSARY.md
    └── 90_DECISIONS.md
```

---

## Workflows overview

### 1. Full annotation pipeline

```bash
python scripts/run_annotation.py --port 19723 --apply json
```
Connects → reads elements + layouts → evaluates rules → exports `output/SheetNotes.json` + per-sheet files.

### 2. Command discovery

```bash
python scripts/discover_commands.py --port 19723
```
Lists every JSON command and type available in the running Archicad instance.

### 3. Quick demo

```bash
python scripts/quick_demo.py --mock          # offline with synthetic data
python scripts/quick_demo.py --port 19723    # live with real data
```
End-to-end demo that prints element counts, phase summaries, and sample output.

> See [agent_docs/20_WORKFLOWS.md](agent_docs/20_WORKFLOWS.md) for detailed step-by-step execution paths.

---

## Code → Archicad concepts mapping (summary)

| Archicad concept | Code module | Key function / class |
|---|---|---|
| **Elements** (walls, columns, doors…) | `src/extract/elements.py` | `get_all_elements()`, `enrich_elements()` |
| **Renovation Status** (Existing, Demo, New) | `src/extract/renovation.py` | `map_renovation_value()`, `classify_elements_by_phase()` |
| **Properties** (read/write) | `src/extract/properties.py` | `resolve_property_ids()`, `get_property_values()`, `set_property_values()` |
| **Layouts** (sheets in Layout Book) | `src/extract/layouts.py` | `get_layouts()`, `get_navigator_tree()` |
| **Drawings** (views placed on layouts) | `src/extract/layouts.py` | `get_drawings_on_layout()` |
| **Classifications** (e.g., Plumbing Fixture) | `src/models/data_model.py` | `ACElement.classification` |
| **Disciplines** (A, S, M, P, E…) | `src/models/data_model.py` | `Discipline` enum, `parse_sheet_id()` |
| **Custom property (notes)** | `src/apply/property_writer.py` | `ensure_custom_property()`, `write_notes_to_layouts()` |
| **Navigator tree** | `src/extract/layouts.py` | `get_navigator_tree()` |
| **Add-On commands** | `src/apply/text_placer.py` | `place_text_on_layout()` via `ExecuteAddOnCommand` |

> See [agent_docs/40_CODE_TO_ARCHICAD_MAP.md](agent_docs/40_CODE_TO_ARCHICAD_MAP.md) for the full mapping with every function and class.

---

## Configuration

### Phases (`config/phases.json`)

Defines the 3 renovation phases: Existing (ac_status=1), Demolition (2), New Construction (3). Extend by adding entries and matching rules.

### Rules (`config/rules.json`)

4 rules ship by default:

| Rule | Fires when… | Injects |
|---|---|---|
| `demo_elements_present` | Demolition elements on sheet | Demolition Notes |
| `new_walls_present` | New Construction walls on sheet | New Work Notes |
| `plumbing_fixtures_present` | Plumbing Fixture classification | Plumbing Coordination |
| `existing_to_remain` | Existing elements on sheet | Existing Conditions Notes |

**Condition types**: `phase_elements_on_sheet`, `phase_element_type_on_sheet`, `element_classification_on_sheet`.

### Templates (`config/note_templates.json`)

Boilerplate text for each note section. Global notes (general + code) are always included. Rule-triggered templates are injected per-sheet.

### Manual overrides (`config/manual_overrides.json`)

Optional per-sheet overrides:
```json
{
  "A-101": {
    "scope_notes": ["First floor demolition scope ..."],
    "manual_notes": ["Coordinate with tenant relocation"]
  }
}
```

> See [agent_docs/50_CONFIG_AND_SECRETS.md](agent_docs/50_CONFIG_AND_SECRETS.md) for full schema documentation.

---

## Testing

```bash
pytest tests/ -v
```

All 15 tests run **offline** with mock data — no Archicad required. Tests cover rule evaluation, note building, sheet ID parsing, and JSON serialization.

---

## Troubleshooting / FAQ

| Problem | Solution |
|---|---|
| `ImportError: archicad` | `pip install archicad` |
| `ConnectionRefusedError` | Enable Archicad JSON API on port 19723 |
| Exit code 127 | Use `python3` explicitly; check PATH |
| Property write fails | Create `LayoutAnnotation > SheetNotesText` manually in Property Manager |
| Notes identical on every sheet | Expected (conservative approach); per-layout filtering is a future enhancement |
| `rules.json` not found | Run from repo root; paths are relative to `config/` |

> See [agent_docs/60_TROUBLESHOOTING.md](agent_docs/60_TROUBLESHOOTING.md) for detailed debugging steps.

---

## Agent documentation

The `agent_docs/` folder contains structured documentation designed for LLM agents and new engineers. Each file has a "Context-switch recap" section with 10 bullet points for fast re-orientation.

| File | Contents |
|---|---|
| [00_START_HERE.md](agent_docs/00_START_HERE.md) | Orientation, repo map, quick reference |
| [10_ARCHITECTURE.md](agent_docs/10_ARCHITECTURE.md) | Three-layer design, data flow, module responsibilities |
| [20_WORKFLOWS.md](agent_docs/20_WORKFLOWS.md) | Step-by-step execution paths for all workflows |
| [30_ARCHICAD_INTEGRATION.md](agent_docs/30_ARCHICAD_INTEGRATION.md) | Live AC connection guide, smoke test, execution modes |
| [40_CODE_TO_ARCHICAD_MAP.md](agent_docs/40_CODE_TO_ARCHICAD_MAP.md) | Every module mapped to Archicad concepts |
| [50_CONFIG_AND_SECRETS.md](agent_docs/50_CONFIG_AND_SECRETS.md) | All config files, schemas, defaults |
| [60_TROUBLESHOOTING.md](agent_docs/60_TROUBLESHOOTING.md) | Common errors and fixes |
| [70_TESTING.md](agent_docs/70_TESTING.md) | Test strategy, coverage, how to extend |
| [80_GLOSSARY.md](agent_docs/80_GLOSSARY.md) | Archicad, AEC, and codebase terminology |
| [90_DECISIONS.md](agent_docs/90_DECISIONS.md) | Architecture decisions and tradeoffs |

---

## License

Private / internal use.
