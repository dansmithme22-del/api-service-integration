# 50 — CONFIG AND SECRETS

## Purpose

Documents every configuration file, environment variable, and secret used by the system. Explains the schema, default values, and how to customize.

## When to read this

- When modifying rules, templates, or phase definitions.
- When setting up a new project or environment.
- When debugging unexpected note content or missing configuration.

---

## Overview

This project uses **JSON configuration files only**. There are:

- **No `.env` files**
- **No environment variables** (port is a CLI argument)
- **No Docker or CI configuration**
- **No secrets** (the Archicad API is localhost-only, no authentication)

---

## Configuration files

### `config/phases.json`

**Purpose**: Defines the renovation phases and their Archicad integer status codes.

**Schema**:
```json
{
  "phases": [
    {
      "id": "existing",           // internal ID (used in rules.json)
      "label": "Existing",        // display label (must match Phase enum value)
      "ac_status": 1,             // Archicad's internal integer code
      "description": "..."        // human-readable description
    }
  ],
  "phase_order": ["existing", "demolition", "new_construction"],
  "default_phase": "new_construction"
}
```

**Loaded by**: `src/extract/renovation.py` at import time (module-level).

**Fallback**: If the file is missing or malformed, hardcoded map `{1: Existing, 2: Demolition, 3: New Construction}` is used.

**To extend**: Add a new phase object to the `phases` array. Then:
1. Add a matching member to the `Phase` enum in `src/models/data_model.py`.
2. Add rules in `config/rules.json` that reference the new phase.
3. Add templates in `config/note_templates.json` for the new note sections.

---

### `config/rules.json`

**Purpose**: Defines annotation rules. Each rule has a condition (when to fire) and a note section (what to inject).

**Schema**:
```json
{
  "rules": [
    {
      "id": "demo_elements_present",        // unique rule ID
      "description": "...",                  // human-readable
      "condition": {
        "type": "phase_elements_on_sheet",   // condition evaluator key
        "phase": "demolition",               // phase to check
        "min_count": 1                       // minimum elements needed
      },
      "note_section": {
        "section_title": "DEMOLITION NOTES", // heading in output
        "template_key": "demolition_notes"   // key in note_templates.json
      }
    }
  ]
}
```

**Loaded by**: `src/decide/rules_engine.py::load_rules()`.

**Current rules** (4 rules):

| Rule ID | Condition type | Fires when… | Injects template |
|---|---|---|---|
| `demo_elements_present` | `phase_elements_on_sheet` | ≥1 demolition element on sheet | `demolition_notes` |
| `new_walls_present` | `phase_element_type_on_sheet` | ≥1 new Wall element on sheet | `new_work_notes` |
| `plumbing_fixtures_present` | `element_classification_on_sheet` | Elements classified as "Plumbing Fixture" | `plumbing_coordination` |
| `existing_to_remain` | `phase_elements_on_sheet` | ≥1 existing element on sheet | `existing_conditions` |

**Condition types available**:

| Type | Parameters | Evaluator |
|---|---|---|
| `phase_elements_on_sheet` | `phase`, `min_count` | `_eval_phase_elements_on_sheet()` |
| `phase_element_type_on_sheet` | `phase`, `element_type`, `min_count` | `_eval_phase_element_type_on_sheet()` |
| `element_classification_on_sheet` | `classification` | `_eval_element_classification_on_sheet()` |

**To add a new rule**: Add a JSON object to the `rules` array with a unique `id`, a `condition` matching one of the available types, and a `note_section` pointing to a template.

---

### `config/note_templates.json`

**Purpose**: Boilerplate note text organized into templates. Rules reference these by `template_key`.

**Schema**:
```json
{
  "global_project_notes": {
    "general_notes": ["line1", "line2", ...],     // always included on every sheet
    "code_notes": ["line1", "line2", ...]          // always included on every sheet
  },
  "templates": {
    "<template_key>": {
      "section_title": "SECTION HEADING",
      "lines": ["line1", "line2", ...]
    }
  },
  "scope_note_placeholder": "...",
  "manual_note_placeholder": "..."
}
```

**Loaded by**: `src/decide/rules_engine.py::load_templates()` and `src/decide/note_builder.py`.

**Current templates**:

| Template key | Section title | Lines |
|---|---|---|
| `demolition_notes` | DEMOLITION NOTES | 5 lines about field verify, disposal, protection, utilities, patching |
| `new_work_notes` | NEW WORK NOTES | 4 lines about partitions, fire-stopping, coordination, barriers |
| `plumbing_coordination` | PLUMBING COORDINATION | 3 lines about fixture locations, backing, rough-in |
| `existing_conditions` | EXISTING CONDITIONS NOTES | 3 lines about as-built docs, field verify, discrepancies |

**To add a new template**: Add a key under `templates` with `section_title` and `lines`. Then create a rule that references it via `template_key`.

---

### `config/sheet_conventions.json`

**Purpose**: Defines the sheet numbering convention (prefix → discipline mapping).

**Schema**:
```json
{
  "pattern": "^(?P<discipline>[A-Z]+)-(?P<number>\\d+)$",
  "disciplines": {
    "A": {"name": "Architectural", "label": "Architectural"},
    "S": {"name": "Structural", "label": "Structural"},
    ...
  },
  "examples": ["A-101", "S-101", ...]
}
```

**Currently loaded by**: This config is **not dynamically loaded** at runtime. The `_PREFIX_MAP` in `src/models/data_model.py` is hardcoded to match. The config file exists as a reference/documentation artifact.

**Known gap**: The code should load `sheet_conventions.json` dynamically instead of hardcoding `_PREFIX_MAP`. This is a straightforward enhancement.

---

### `config/manual_overrides.json` (optional)

**Purpose**: Per-sheet scope notes and manual notes that supplement the rule-generated content.

**Schema**:
```json
{
  "<sheet_id>": {
    "scope_notes": ["line1", "line2"],
    "manual_notes": ["line1", "line2"]
  }
}
```

**Loaded by**: `src/decide/note_builder.py::_load_manual_overrides()`.

**Behavior**: If the file doesn't exist, an empty dict is returned (no error). This is fully optional.

---

## CLI arguments (runtime configuration)

| Argument | Script(s) | Default | Description |
|---|---|---|---|
| `--port` | All three scripts | `19723` | Archicad JSON API port |
| `--apply` | `run_annotation.py` | `json` | Output mode: `json`, `property`, `both` |
| `--dry-run` | `run_annotation.py` | `false` | Preview only, no output |
| `--project-name` | `run_annotation.py` | `""` | Project name in output metadata |
| `--mock` | `quick_demo.py` | `false` | Use synthetic data |

---

## Hardcoded defaults

| Constant | Location | Value | Description |
|---|---|---|---|
| `DEFAULT_PORT` | `src/connection.py` | `19723` | Default Archicad JSON port |
| `PROPERTY_GROUP` | `src/apply/property_writer.py` | `"LayoutAnnotation"` | Custom property group name |
| `PROPERTY_NAME` | `src/apply/property_writer.py` | `"SheetNotesText"` | Custom property name |
| `_ELEMENT_TYPES` | `src/extract/elements.py` | 17 types | Fallback element type list |
| `_PREFIX_MAP` | `src/models/data_model.py` | A→Architectural, etc. | Sheet prefix → discipline mapping |
| `_OUTPUT_DIR` | `src/apply/json_exporter.py` | `<repo>/output/` | Default output directory |
| `_CONFIG_PATH` (phases) | `src/extract/renovation.py` | `config/phases.json` | Phase config file path |
| `_RULES_PATH` | `src/decide/rules_engine.py` | `config/rules.json` | Rules file path |
| `_TEMPLATES_PATH` | `src/decide/rules_engine.py` | `config/note_templates.json` | Templates file path |

---

## Context-switch recap

1. **No secrets, no `.env`, no Docker, no CI.** Configuration is JSON files in `config/`.
2. Four config files: `phases.json`, `rules.json`, `note_templates.json`, `sheet_conventions.json`.
3. One optional config: `manual_overrides.json` (per-sheet manual notes).
4. `sheet_conventions.json` is **not dynamically loaded** — the code uses a hardcoded `_PREFIX_MAP`.
5. Rules reference templates by `template_key`. Templates define `section_title` + `lines`.
6. Three condition types are available: `phase_elements_on_sheet`, `phase_element_type_on_sheet`, `element_classification_on_sheet`.
7. Port is the only runtime parameter (CLI `--port`, default 19723).
8. Custom property names (`LayoutAnnotation` / `SheetNotesText`) are hardcoded constants.
9. All config paths are resolved relative to the repo root using `Path(__file__).resolve().parents[2]`.
10. Phase config has a hardcoded fallback if the JSON file is missing.
