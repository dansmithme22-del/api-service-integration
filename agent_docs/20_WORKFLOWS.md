# 20 — WORKFLOWS

## Purpose

Step-by-step documentation of **every workflow** in the codebase. Each workflow includes the user story, inputs, execution path, outputs, failure modes, and extension points.

## When to read this

- When tracing how data flows through the system end-to-end.
- When debugging a specific pipeline stage.
- When adding a new workflow or modifying an existing one.

---

## Workflow 1: Full Annotation Pipeline (`scripts/run_annotation.py`)

### User story

> As an architect working on a renovation project in Archicad, I want the system to automatically read my model, determine which sheets need demolition/new-work/plumbing notes, and either export those notes as JSON or write them into Archicad properties — so my sheet notes stay in sync with the model without manual editing.

### Inputs

| Input | Source | Required? |
|---|---|---|
| `--port` (int) | CLI argument, default `19723` | No (has default) |
| `--apply` (`json`\|`property`\|`both`) | CLI argument, default `json` | No |
| `--dry-run` (flag) | CLI argument | No |
| `--project-name` (str) | CLI argument, default `""` | No |
| `config/rules.json` | File on disk | Yes |
| `config/note_templates.json` | File on disk | Yes |
| `config/phases.json` | File on disk | Yes (falls back to hardcoded) |
| `config/manual_overrides.json` | File on disk | No (optional) |
| Running Archicad instance | TCP on localhost | Yes |

### Step-by-step execution path

```
scripts/run_annotation.py::main()
│
├─ 1. CONNECT
│     ArchicadConnection(port).connect()
│     → src/connection.py: imports archicad.ACConnection, calls .connect(port)
│     → establishes TCP connection to Archicad on localhost:<port>
│     → stores _conn, _commands, _types, _utilities
│
├─ 2. EXTRACT
│  ├─ 2a. get_all_elements(conn)
│  │     → src/extract/elements.py
│  │     → calls conn.commands.GetAllElements()
│  │     → returns list[dict] with {guid, element_type}
│  │
│  ├─ 2b. enrich_elements(conn, raw_elements)
│  │     → src/extract/elements.py
│  │     → resolves property IDs for: General_ElementLayer, General_FloorNumber, General_RenovationStatus
│  │     → calls GetPropertyValuesOfElements for all elements
│  │     → maps renovation values via src/extract/renovation.py::map_renovation_value()
│  │     → returns list[ACElement] with full layer/story/phase/properties data
│  │
│  ├─ 2c. phase_summary(elements)
│  │     → src/extract/renovation.py
│  │     → returns {phase_name: count} dict (logged only)
│  │
│  └─ 2d. get_layouts(conn)
│        → src/extract/layouts.py
│        → calls GetNavigatorItemTree("LayoutBook")
│        → walks tree recursively, extracts items with type "Layout"
│        → parses sheet_id and discipline from layout name (e.g., "A-101" → Architectural)
│        → returns list[ACLayout]
│
├─ 3. DECIDE
│  ├─ 3a. analyse_all_layouts(layouts, elements)
│  │     → src/decide/phase_analyzer.py
│  │     → for each layout, counts elements per phase, per element type, per classification
│  │     → returns dict[layout_guid → LayoutPhaseReport]
│  │     ⚠ Note: currently attributes ALL elements to EVERY layout (conservative)
│  │       because per-layout element filtering is not yet implemented
│  │
│  └─ 3b. build_all_notes(layouts, reports, project_name)
│        → src/decide/note_builder.py
│        → loads config/rules.json, config/note_templates.json, config/manual_overrides.json
│        → for each layout:
│        │   → evaluate_rules(report, rules, templates)
│        │       → src/decide/rules_engine.py
│        │       → iterates rules, evaluates condition against LayoutPhaseReport
│        │       → for each fired rule, looks up template_key in note_templates.json
│        │       → returns list[NoteEntry]
│        │   → combines: global_notes + triggered_notes + manual_overrides
│        │   → returns SheetNotes
│        → returns ProjectNotesOutput
│
├─ 3.5 DRY-RUN CHECK
│     → if --dry-run: print JSON to stdout and exit
│
└─ 4. APPLY
   ├─ 4a. --apply json (or both)
   │     → src/apply/json_exporter.py
   │     → export_json(notes) → output/SheetNotes.json
   │     → export_per_sheet_files(notes) → output/per_sheet/<sheet_id>.json
   │     → export_flat_text(notes) → output/flat_text/<sheet_id>.txt
   │
   └─ 4b. --apply property (or both)
         → src/apply/property_writer.py
         → ensure_custom_property(conn) — resolves or creates LayoutAnnotation_SheetNotesText
         → write_notes_to_layouts(conn, layouts, sheet_notes_map)
         → for each layout: SetPropertyValuesOfElements with flat text
```

### Outputs

| Mode | Output location | Description |
|---|---|---|
| `--apply json` | `output/SheetNotes.json` | Complete project notes (all sheets) |
| `--apply json` | `output/per_sheet/<sheet_id>.json` | One JSON file per sheet |
| `--apply json` | `output/flat_text/<sheet_id>.txt` | Plain text per sheet (for pasting) |
| `--apply property` | Archicad property `LayoutAnnotation_SheetNotesText` | Custom property on each Layout element |
| `--dry-run` | stdout | JSON dump of ProjectNotesOutput |

### Failure modes

| Failure | Symptom | Fix |
|---|---|---|
| Archicad not running | `ConnectionError` at step 1 | Start Archicad, enable JSON API |
| `archicad` package not installed | `ImportError` at step 1 | `pip install archicad` |
| No layouts in LayoutBook | Warning log, `sys.exit(0)` | Create layouts in Archicad |
| Property not resolvable | Warning in step 2b, elements returned without enrichment | Check AC property definitions |
| Custom property doesn't exist | Warning in step 4b, 0 layouts updated | Create property manually in Property Manager |
| rules.json missing/malformed | `FileNotFoundError` or `json.JSONDecodeError` | Fix config file |

### Extension points

- **New rule condition type**: Add evaluator function in `rules_engine.py`, register in `_EVALUATORS`.
- **New note template**: Add template in `note_templates.json` under `templates` key.
- **New apply strategy**: Add module in `src/apply/`, call from `run_annotation.py`.
- **Per-layout element filtering**: Implement `layout_element_map` in the pipeline (currently not wired).

---

## Workflow 2: Command Discovery (`scripts/discover_commands.py`)

### User story

> As a developer, I want to see every JSON command and type available in my running Archicad instance — so I know what API surface I can use.

### Inputs

| Input | Source |
|---|---|
| `--port` (int) | CLI argument, default `19723` |
| Running Archicad instance | TCP on localhost |

### Execution path

```
scripts/discover_commands.py::main()
│
├─ 1. ArchicadConnection(port).connect()
│
├─ 2. discover_commands(conn)
│     → src/discovery.py
│     → iterates dir(conn.commands), filters callables
│     → gets signature + docstring for each
│     → returns list[{name, doc, sig}]
│
├─ 3. discover_types(conn)
│     → iterates dir(conn.types), filters non-private
│     → returns list[str]
│
├─ 4. Print to stdout (formatted)
│
└─ 5. Write output/available_commands.json
```

### Outputs

- **stdout**: Formatted list of commands with signatures and docs.
- **output/available_commands.json**: Machine-readable JSON with `commands` and `types` arrays.

### Failure modes

- Connection failure → printed error message with instructions to enable JSON API.

---

## Workflow 3: Quick Demo (`scripts/quick_demo.py`)

### User story

> As a new developer or stakeholder, I want to see the entire pipeline working end-to-end in 30 seconds — either with mock data or a live Archicad connection.

### Inputs

| Input | Source |
|---|---|
| `--port` (int) | CLI argument, default `19723` |
| `--mock` (flag) | CLI argument — use synthetic data |

### Execution path

**Mock mode** (`--mock`):
```
quick_demo.py::main()
├─ _mock_elements() → 8 synthetic ACElement objects (walls, columns, objects, slabs, doors)
├─ _mock_layouts() → 3 synthetic ACLayout objects (A-101, A-102, P-101)
└─ _run_decide_and_export(elements, layouts)
    ├─ analyse_all_layouts()
    ├─ build_all_notes()
    ├─ print JSON sample to stdout
    └─ export_json() → output/SheetNotes.json
```

**Live mode** (no `--mock`):
```
quick_demo.py::main()
├─ _live_demo(port)
│   ├─ connect to Archicad
│   ├─ discover_commands() → print first 20
│   ├─ get_all_elements() → print count
│   ├─ enrich_elements(first 50) → print count
│   ├─ phase_summary() → print
│   ├─ get_layouts() → print first 10
│   └─ _run_decide_and_export()
└─ on failure → falls back to mock mode
```

### Outputs

- **stdout**: Element counts, phase summary, layout list, sample JSON, flat text for first sheet.
- **output/SheetNotes.json**: Full export (same as workflow 1 with `--apply json`).

---

## Data flow summary (all workflows)

```
Archicad
  ↓ GetAllElements, GetPropertyValuesOfElements, GetNavigatorItemTree
list[ACElement] + list[ACLayout]
  ↓ analyse_all_layouts()
dict[guid → LayoutPhaseReport]
  ↓ evaluate_rules() per layout
list[NoteEntry] per layout
  ↓ build_sheet_notes() per layout
list[SheetNotes]
  ↓ build_all_notes()
ProjectNotesOutput
  ↓ export_json() / write_notes_to_layouts()
output/SheetNotes.json   OR   Archicad custom property
```

---

## Context-switch recap

1. Three workflows exist: **run_annotation** (full pipeline), **discover_commands** (API enumeration), **quick_demo** (demo/smoke test).
2. `run_annotation.py` is the primary workflow — it does Extract → Decide → Apply.
3. The `--dry-run` flag skips the Apply layer entirely.
4. `--apply json` is safe (no AC mutation); `--apply property` writes to AC.
5. `quick_demo.py --mock` runs the entire Decide + Apply pipeline with synthetic data — no Archicad needed.
6. All extracted elements are currently attributed to every layout (conservative approach). Per-layout filtering is a future enhancement.
7. Rule evaluation is per-layout: each layout gets its own `LayoutPhaseReport` and independent rule evaluation.
8. Config files are loaded at Decide time from `config/` relative to repo root.
9. Manual overrides are optional and keyed by `sheet_id` (e.g., `"A-101": {...}`).
10. Output files are always written to the `output/` directory (configurable via function params).
