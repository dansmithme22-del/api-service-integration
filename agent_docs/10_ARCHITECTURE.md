# 10 — ARCHITECTURE

## Purpose

Deep-dive into the system's three-layer architecture, data flow, module responsibilities, and how the layers interconnect.

## When to read this

- When you need to understand **why** the code is structured the way it is.
- Before adding a new feature or refactoring an existing module.
- When you need to trace data from Archicad through the pipeline to the output.

---

## High-level overview

```
┌──────────────────────────────────────────────────────────────┐
│  Archicad 29  (running, JSON API enabled on port 19723)      │
└────────────────────────┬─────────────────────────────────────┘
                         │  TCP / JSON  (localhost:19723)
┌────────────────────────▼─────────────────────────────────────┐
│  Python                                                      │
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │ EXTRACT  │───►│  DECIDE  │───►│  APPLY   │              │
│   │ Layer 1  │    │  Layer 2 │    │  Layer 3 │              │
│   └──────────┘    └──────────┘    └──────────┘              │
│                                                              │
│   Shared: src/models/data_model.py  (Pydantic)              │
│   Config: config/*.json                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Extract (`src/extract/`)

**Responsibility**: Read data from a live Archicad instance and produce typed Pydantic models.

| Module | Responsibility | Key functions | Archicad commands used |
|---|---|---|---|
| `elements.py` | Read all model elements (walls, columns, doors, etc.) | `get_all_elements()`, `enrich_elements()` | `GetAllElements`, `GetElementsByType` |
| `layouts.py` | Read navigator tree, extract Layout sheets | `get_layouts()`, `get_drawings_on_layout()` | `GetNavigatorItemTree` |
| `properties.py` | Resolve property names → IDs, read/write property values | `resolve_property_ids()`, `get_property_values()`, `set_property_values()` | `GetPropertyIds`, `GetPropertyValuesOfElements`, `SetPropertyValuesOfElements` |
| `renovation.py` | Map raw renovation status (int/string) to `Phase` enum | `map_renovation_value()`, `classify_elements_by_phase()` | — (operates on extracted data) |

### Data produced

- `list[ACElement]` — every element with GUID, type, layer, story, renovation status, properties.
- `list[ACLayout]` — every layout with GUID, name, sheet_id, discipline, drawings.
- `ModelSnapshot` — timestamp + project name + all elements + all layouts.

---

## Layer 2: Decide (`src/decide/`)

**Responsibility**: Evaluate rules against extracted data and produce `SheetNotes` models.

| Module | Responsibility | Key classes/functions |
|---|---|---|
| `phase_analyzer.py` | Group elements by phase per layout; produce `LayoutPhaseReport` | `LayoutPhaseReport`, `analyse_layout()`, `analyse_all_layouts()` |
| `rules_engine.py` | Load rules from config, evaluate conditions, return triggered `NoteEntry` objects | `load_rules()`, `load_templates()`, `evaluate_rules()` |
| `note_builder.py` | Assemble complete `SheetNotes` per layout by combining global notes + rule-triggered notes + manual overrides | `build_sheet_notes()`, `build_all_notes()` |

### Rule evaluation flow

```
For each layout:
  1. LayoutPhaseReport = analyse_layout(layout, elements)
       → counts elements per Phase
       → counts element types per Phase
       → counts classifications

  2. For each rule in config/rules.json:
       → evaluate condition against LayoutPhaseReport
       → if condition fires → look up template in note_templates.json → produce NoteEntry

  3. build_sheet_notes combines:
       → global_project_notes (from note_templates.json)
       → triggered NoteEntry objects (from rules)
       → scope_notes + manual_notes (from manual_overrides.json, keyed by sheet_id)
       → outputs a SheetNotes model
```

### Condition types (extensible)

| Condition type | What it checks | Config keys |
|---|---|---|
| `phase_elements_on_sheet` | ≥ `min_count` elements of a given `phase` | `phase`, `min_count` |
| `phase_element_type_on_sheet` | ≥ `min_count` of a specific `element_type` in a `phase` | `phase`, `element_type`, `min_count` |
| `element_classification_on_sheet` | Elements with a matching `classification` string | `classification` |

To add a new condition type: add an evaluator function in `rules_engine.py` and register it in the `_EVALUATORS` dict.

---

## Layer 3: Apply (`src/apply/`)

**Responsibility**: Push results back to Archicad or export to disk.

| Module | Strategy | Mutates Archicad? | Output |
|---|---|---|---|
| `json_exporter.py` | Write JSON/text files to `output/` | **No** | `SheetNotes.json`, `per_sheet/<id>.json`, `flat_text/<id>.txt` |
| `property_writer.py` | Write note text to a custom property on Layout elements | **Yes** | Custom property `LayoutAnnotation_SheetNotesText` on each layout |
| `text_placer.py` | Place 2D text elements directly on layouts | **Yes** (if available) | Text elements on layout sheets |

### Apply strategy detail

**JSON Export** (safe, default):
- `export_json()` → single `output/SheetNotes.json`
- `export_per_sheet_files()` → `output/per_sheet/A-101.json`, etc.
- `export_flat_text()` → `output/flat_text/A-101.txt`, etc.

**Property Writer** (mutates AC):
1. Ensures custom property `LayoutAnnotation_SheetNotesText` exists (attempts `CreatePropertyDefinition`, falls back to manual instruction).
2. For each layout, calls `SetPropertyValuesOfElements` with the flattened note text.
3. A GDL object on the Master Layout reads this property via AutoText or `REQUEST` and renders it.

**Text Placer** (stub):
- Attempts `CreateTextElement` JSON command (doesn't exist in AC 29).
- Falls back to `ExecuteAddOnCommand` targeting the C++ Add-On `LayoutAnnotator::PlaceText`.
- If neither available, logs a warning and returns `False`.

---

## Shared data model (`src/models/data_model.py`)

All layers communicate through Pydantic models:

```
ProjectNotesOutput
├── project_name: str
├── generated_at: datetime
├── global_general_notes: list[str]
├── global_code_notes: list[str]
└── sheets: list[SheetNotes]
       ├── sheet_id: str                      ("A-101")
       ├── sheet_name: str
       ├── discipline: Discipline             (enum: Architectural, Structural, …)
       ├── general_notes: list[str]           (from templates)
       ├── code_notes: list[str]              (from templates)
       ├── phase_notes: dict[str, list[str]]  (currently unused, reserved)
       ├── element_driven_notes: list[NoteEntry]
       │     ├── trigger_rule_id: str
       │     ├── section_title: str
       │     └── body: list[str]
       ├── scope_notes: list[str]             (from manual_overrides.json)
       └── manual_notes: list[str]            (from manual_overrides.json)
```

Supporting models:
- `ACElement` — single element (guid, type, layer, story, renovation_status, classification, properties)
- `ACDrawing` — drawing placed on a layout (guid, name, source view info)
- `ACLayout` — layout sheet (guid, name, sheet_id, discipline, drawings)
- `ModelSnapshot` — full extract snapshot (timestamp, project name, elements, layouts)
- `Phase` — enum: Existing, Demolition, New Construction
- `Discipline` — enum: Architectural, Structural, Mechanical, Plumbing, Electrical, Fire Protection, Landscape, Civil, General, Unknown

---

## Connection model (`src/connection.py`)

```
ArchicadConnection
├── __init__(port=19723)
├── connect() → self            # calls archicad.ACConnection.connect(port)
├── connected: bool
├── commands                    # SDK commands namespace
├── types                       # SDK types namespace
├── utilities                   # SDK utilities namespace
└── execute_raw(cmd, params)    # raw JSON command (for non-SDK commands)
```

- `execute_raw()` tries the SDK's `.request()` method first, then falls back to raw HTTP POST to `http://127.0.0.1:<port>`.
- All other modules receive an `ArchicadConnection` instance — they never import the `archicad` package directly.

---

## Dependency direction

```
scripts/run_annotation.py
    ├── src/connection.py
    ├── src/extract/*           ← depends on connection + models
    ├── src/decide/*            ← depends on models + config (NO connection dependency)
    └── src/apply/*             ← depends on connection + models + extract.properties
```

Key constraint: **Decide layer has NO dependency on the Archicad connection.** It operates purely on data models and config files. This is what makes offline testing possible.

---

## Context-switch recap

1. Three layers: **Extract** (read AC) → **Decide** (rules) → **Apply** (write back/export).
2. All layers communicate through Pydantic models in `src/models/data_model.py`.
3. `ArchicadConnection` in `src/connection.py` is the single AC contact point.
4. Decide layer is **connection-free** — fully testable offline.
5. Apply has three strategies: JSON export (safe), property write (mutating), text placement (stub).
6. Rules engine uses a registry pattern (`_EVALUATORS` dict) — easy to extend.
7. Config drives behavior: `rules.json` (conditions), `note_templates.json` (boilerplate), `phases.json` (phase mapping).
8. `execute_raw()` allows calling any JSON command, including Add-On commands.
9. The C++ Add-On is optional and only needed for direct 2D text placement on layouts.
10. Dependencies flow inward: scripts → src layers → models. Never the reverse.
