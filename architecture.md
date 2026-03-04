# Layout Annotation Automation — Architecture

## Overview

This system automatically generates and maintains layout sheet notes and
view/drawing annotations in Archicad 29, driven by the model, renovation phases,
and manual inputs.

---

## Two Approaches

### Approach A — Python-Only (Recommended Start)

```
┌──────────────────────────────────────────────────────────────┐
│  Archicad 29 (running, JSON Command API enabled on port)     │
└────────────────────────┬─────────────────────────────────────┘
                         │  TCP / JSON
┌────────────────────────▼─────────────────────────────────────┐
│  Python  (archicad PyPI + this repo)                         │
│                                                              │
│   EXTRACT  ─►  DECIDE  ─►  APPLY                            │
│   (read model)  (rules)     (write properties / export JSON) │
└──────────────────────────────────────────────────────────────┘
```

**How notes reach sheets:**

| Strategy | Mechanism | Pros | Cons |
|---|---|---|---|
| **Property-driven** | Write to custom IFC/User properties on Layout elements. GDL title-block or notes object reads them via AutoText (`LAYOUT_*` globals or `REQUEST` property). | Survives re-publish; stable on re-open. | Requires a GDL notes object placed on each master layout. |
| **External JSON** | Export `SheetNotes.json`. A custom GDL object or separate process reads it. | No property pollution; easy to version. | Extra step to import; GDL `OPEN` is limited. |
| **Direct text placement** | Use `CreateTextElement` JSON command (if available in AC29). | True WYSIWYG. | Command may not exist → need C++ fallback. |

**Recommended flow (property-driven):**

1. Python reads all elements visible on each Layout/View via navigator tree.
2. Python evaluates rules (phase, element type, discipline).
3. Python writes results to custom properties on the Layout.
4. A GDL "Sheet Notes" object on the Master Layout reads those properties
   and renders the notes as text.

### Approach B — Hybrid (Python + C++ Add-On)

Use when Python API cannot:
- Place or modify 2D text/labels on layouts directly.
- Read the exact "elements visible on this drawing" list.

```
  Python (extract + decide)
       │
       ▼ writes SheetNotes.json
  C++ Add-On (reads JSON, places/updates ACAPI text elements on layouts)
```

The C++ Add-On uses `ACAPI_Element_Create` / `ACAPI_Element_Change` with
`API_TextType` or `API_LabelType` elements. See `addons/layout_annotator_cpp/`.

---

## Three-Layer Architecture

```
src/
├── extract/          # Layer 1: Read from Archicad
│   ├── elements.py       → element GUIDs, types, layers
│   ├── layouts.py        → navigator tree, layout list, placed drawings
│   ├── properties.py     → property definitions + values
│   └── renovation.py     → renovation status per element
│
├── decide/           # Layer 2: Evaluate rules, build notes
│   ├── rules_engine.py   → match rules against extracted data
│   ├── note_builder.py   → assemble final note text per sheet
│   └── phase_analyzer.py → classify elements by phase per layout
│
├── apply/            # Layer 3: Push results back
│   ├── property_writer.py → set custom properties on layouts
│   ├── json_exporter.py   → write SheetNotes.json
│   └── text_placer.py     → (stub) direct text placement
│
└── models/           # Shared data model (Pydantic)
    └── data_model.py
```

Each layer is independently testable. You can run Extract → Decide → inspect
JSON without ever writing back to Archicad.

---

## Data Model Summary

```
ProjectNotes          (global boilerplate for ALL sheets)
  ├── general_notes   : list[str]
  └── code_notes      : list[str]

SheetNotes            (per layout)
  ├── sheet_id        : str              (e.g. "A-101")
  ├── sheet_name      : str
  ├── discipline      : str              (Architectural, Structural, …)
  ├── phase_notes     : dict[Phase, list[str]]
  ├── element_driven  : list[NoteEntry]
  ├── manual_notes    : list[str]
  └── scope_notes     : list[str]

NoteEntry
  ├── trigger         : str              ("demo_walls_present")
  ├── section_title   : str              ("Demolition Notes")
  └── body            : list[str]

Phase = Literal["Existing", "Demolition", "New Construction"]
```

See `src/models/data_model.py` for the full Pydantic definitions.

---

## Key Archicad JSON Commands Used

| Command | Purpose | Discovery |
|---|---|---|
| `GetAllElements` | List all element GUIDs in model | built-in |
| `GetDetailsOfElements` | Element type, layer, story | built-in |
| `GetPropertyValuesOfElements` | Read any property by ID | built-in |
| `GetAllPropertyNames` | Enumerate property groups + names | built-in |
| `GetPropertyIds` | Resolve property name → ID | built-in (AC27+) |
| `SetPropertyValuesOfElements` | Write property values | built-in |
| `GetNavigatorItemTree` | Full navigator (layouts, views) | built-in |
| `GetBuildingMaterialPhysicalProperties` | Material info | built-in |
| `ExecuteAddOnCommand` | Invoke C++ add-on commands | built-in |

If a command doesn't exist, the discovery script (`scripts/discover_commands.py`)
will list everything available so you know exactly what's there.

---

## Milestones

| # | Milestone | Deliverable |
|---|---|---|
| 1 | **Connection & Discovery** | Connect to AC29; list all commands; confirm property access |
| 2 | **Model Extraction** | Read elements, renovation status, layers, stories |
| 3 | **Layout Mapping** | Map navigator layouts → placed drawings → source views → elements |
| 4 | **Rules Engine v1** | Evaluate phase rules + element-type rules; produce SheetNotes.json |
| 5 | **Property-Driven Apply** | Create custom properties; write note text to layouts |
| 6 | **GDL Notes Object** | Title-block or standalone GDL object reads properties, renders notes |
| 7 | **Full Pipeline Script** | One-click `run_annotation.py` end-to-end |
| 8 | **C++ Add-On (optional)** | Direct text placement if property approach insufficient |
