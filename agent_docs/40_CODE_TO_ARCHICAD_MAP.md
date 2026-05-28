# 40 — CODE TO ARCHICAD MAP

## Purpose

Maps every module, class, and function in this codebase to the **specific Archicad concept** it reads, writes, or operates on. Use this as a lookup table when you need to find "where in the code does X Archicad feature get touched?"

## When to read this

- When you need to modify how the system interacts with a specific Archicad feature.
- When adding support for a new Archicad concept (e.g., Zones, Schedules, Labels).
- When debugging unexpected behavior related to a specific Archicad artifact.

---

## Master mapping table

### Elements

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Elements** (Walls, Columns, Beams, Slabs, Roofs, Doors, Windows, Objects, etc.) | `src/extract/elements.py` | `get_all_elements()`, `enrich_elements()` | Reads all element GUIDs and types from the model. Enriches with layer, story, renovation status. |
| **Element Types** | `src/extract/elements.py` | `_ELEMENT_TYPES` constant | Hardcoded list of 17 element types used as fallback when `GetAllElements` fails. |
| **Element GUIDs** | `src/models/data_model.py` | `ACElement.guid` | Unique identifier for each element, used in all API calls. |

### Renovation / Phases

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Renovation Status** (Existing=1, Demolition=2, New=3) | `src/extract/renovation.py` | `map_renovation_value()`, `_STATUS_MAP`, `_STRING_MAP` | Maps AC's int/string renovation values to the `Phase` enum. |
| **Renovation Filters** | `src/decide/phase_analyzer.py` | `classify_elements_by_phase()`, `analyse_layout()` | Groups elements by their renovation phase per layout. |
| **Phase configuration** | `config/phases.json` | — | Defines the 3 phases with their `ac_status` integer codes. |

### Properties

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Property Definitions** (groups + names) | `src/extract/properties.py` | `get_all_property_names()` | Enumerates all property definitions in the project via `GetAllPropertyNames`. |
| **Property IDs** | `src/extract/properties.py` | `resolve_property_ids()` | Converts human-readable names (e.g., `General_RenovationStatus`) to SDK property ID objects via `GetPropertyIds`. |
| **Property Values (read)** | `src/extract/properties.py` | `get_property_values()` | Batch-reads property values for multiple elements via `GetPropertyValuesOfElements`. |
| **Property Values (write)** | `src/extract/properties.py` | `set_property_values()` | Batch-writes property values via `SetPropertyValuesOfElements`. |
| **Custom Property: `LayoutAnnotation_SheetNotesText`** | `src/apply/property_writer.py` | `ensure_custom_property()`, `PROPERTY_GROUP`, `PROPERTY_NAME` | Creates (or resolves) the custom string property used to inject note text into layouts. |
| **Built-in Properties read** | `src/extract/elements.py` | `enrich_elements()` | Reads `General_ElementLayer`, `General_FloorNumber`, `General_RenovationStatus`. |

### Layers

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Layer names** | `src/extract/elements.py` | `enrich_elements()` → `General_ElementLayer` | Reads the layer name of each element. Stored in `ACElement.layer_name`. |

### Stories / Floors

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Story (floor) number** | `src/extract/elements.py` | `enrich_elements()` → `General_FloorNumber` | Reads the story/floor of each element. Stored in `ACElement.story_name`. |

### Navigator / Layout Book

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Navigator Item Tree** | `src/extract/layouts.py` | `get_navigator_tree()` | Retrieves the full LayoutBook tree via `GetNavigatorItemTree("LayoutBook")`. |
| **Layouts (sheets)** | `src/extract/layouts.py` | `get_layouts()`, `_walk_tree()` | Walks the navigator tree, extracts Layout-type items, parses sheet IDs. |
| **Layout elements** | `src/models/data_model.py` | `ACLayout` | Stores guid, layout_name, sheet_id, discipline, master_layout_name, drawings. |
| **Sheet ID parsing** | `src/models/data_model.py` | `parse_sheet_id()` | Extracts discipline prefix + number from names like `"A-101 - FIRST FLOOR PLAN"`. |

### Drawings (placed on Layouts)

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Drawing elements** | `src/extract/layouts.py` | `get_drawings_on_layout()` | Retrieves Drawing elements placed on a specific layout via `GetElementsByType("Drawing")`. |
| **Drawing model** | `src/models/data_model.py` | `ACDrawing` | Stores guid, name, source_view_id, source_view_path. |

### Classifications

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Element classification** (e.g., "Plumbing Fixture") | `src/models/data_model.py` | `ACElement.classification` | Stored as a string. Used by the `element_classification_on_sheet` rule condition. |
| **Classification matching** | `src/decide/phase_analyzer.py` | `LayoutPhaseReport.has_classification()` | Case-insensitive substring match against tracked classifications. |
| **Classification rule** | `src/decide/rules_engine.py` | `_eval_element_classification_on_sheet()` | Evaluates whether elements with a given classification exist on the sheet. |

### Disciplines (Sheet types)

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Discipline enum** | `src/models/data_model.py` | `Discipline` enum | 10 values: Architectural, Structural, Mechanical, Plumbing, Electrical, Fire Protection, Landscape, Civil, General, Unknown. |
| **Prefix → Discipline map** | `src/models/data_model.py` | `_PREFIX_MAP` | Maps sheet prefixes (A, S, M, P, E, FP, L, C, G) to Discipline enum. |
| **Sheet conventions config** | `config/sheet_conventions.json` | — | Defines the regex pattern and prefix-to-discipline mapping (currently loaded at model level, not from this config). |

### AutoText / GDL Property Requests

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **Property-driven notes (GDL reads properties)** | `src/apply/property_writer.py` | Module docstring | The custom property `LayoutAnnotation_SheetNotesText` is designed to be read by a GDL title-block object via `REQUEST ("Property_Value", ...)` or `LAYOUT_*` globals. |

### Text Elements / Labels (2D)

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **2D text placement** (stub) | `src/apply/text_placer.py` | `place_text_on_layout()` | Attempts `CreateTextElement` (not available in AC 29), falls back to `ExecuteAddOnCommand` targeting the C++ Add-On. |

### Add-On Commands

| Archicad concept | Code location | Classes/Functions | What it does |
|---|---|---|---|
| **ExecuteAddOnCommand** | `src/connection.py`, `src/apply/text_placer.py` | `execute_raw()`, `place_text_on_layout()` | Invokes registered C++ Add-On commands via the JSON API. |
| **C++ Add-On: LayoutAnnotator** | `addons/layout_annotator_cpp/` | `PlaceText` command | Skeleton C++ Add-On that creates text elements on layouts via `ACAPI_Element_Create`. |

---

## Archicad concepts NOT yet covered by this codebase

These Archicad features are **not** currently read or written by the code. Listed here for future extension planning.

| Concept | Potential use | Extension point |
|---|---|---|
| **Views** (floor plan views, sections, elevations) | Filter elements visible in a specific view | `src/extract/layouts.py` — currently only reads layouts, not source views |
| **Zones** (rooms/spaces) | Add zone-based notes (e.g., room finish schedules) | Add `src/extract/zones.py`, new rule condition type |
| **Schedules** | Cross-reference schedule data in notes | New extract module |
| **Publisher Sets** | Auto-publish after annotation | New apply module |
| **Title Blocks** | Currently assumed to exist as GDL objects; not created by code | GDL authoring is manual |
| **Labels** | Auto-label elements | `text_placer.py` or C++ Add-On extension |
| **Worksheets** | Place detail notes on worksheets | Extend `layouts.py` to handle worksheet-type navigator items |
| **Master Layouts** | Currently read (`master_layout_name` field) but not used in logic | Could filter rules by master layout |
| **IFC Properties** | Write IFC-specific properties | Extend `property_writer.py` |
| **Building Materials** | Material-based notes | New extract module + rule condition |

---

## Context-switch recap

1. **Elements**: `src/extract/elements.py` reads via `GetAllElements` / `GetElementsByType`.
2. **Renovation Status**: `src/extract/renovation.py` maps int/string → `Phase` enum.
3. **Properties**: `src/extract/properties.py` resolves names → IDs and reads/writes values.
4. **Layouts**: `src/extract/layouts.py` reads the navigator tree, extracts Layout items.
5. **Sheet ID + Discipline**: `data_model.py::parse_sheet_id()` parses from layout names.
6. **Classifications**: Stored on `ACElement`, checked by `element_classification_on_sheet` rule.
7. **Custom property `LayoutAnnotation_SheetNotesText`**: Created/written by `property_writer.py`.
8. **Text placement**: Stub in `text_placer.py`, requires C++ Add-On for real implementation.
9. **GDL integration**: Not in this codebase — a GDL object must be manually created to read the custom property.
10. Views, Zones, Schedules, Publisher Sets, Title Blocks, Labels, Worksheets are **not yet implemented**.
