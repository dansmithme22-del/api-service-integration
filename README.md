# Layout Annotation Automation for Archicad 29

Automatically generate and maintain layout sheet notes and view/drawing
annotations based on the Archicad model, renovation phases, and manual inputs.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the minimal working example (no Archicad needed)
python scripts/quick_demo.py --mock

# 3. With Archicad running (JSON API enabled on port 19723):
python scripts/discover_commands.py          # see what's available
python scripts/quick_demo.py                 # small demo
python scripts/run_annotation.py --dry-run   # full pipeline, preview only
python scripts/run_annotation.py             # full pipeline, export JSON
```

## Architecture

See [architecture.md](architecture.md) for the full design document.

```
   EXTRACT  →  DECIDE  →  APPLY
   (read AC)   (rules)    (write back / export)
```

### Three-layer design

| Layer | Directory | Purpose |
|---|---|---|
| **Extract** | `src/extract/` | Connect to Archicad, read elements, properties, layouts, renovation status |
| **Decide** | `src/decide/` | Evaluate rules, analyse phases, assemble note text |
| **Apply** | `src/apply/` | Write custom properties, export JSON, place text (C++ fallback) |

### Two approaches

| Approach | When to use |
|---|---|
| **A) Python-only** | Property-driven notes + JSON export. Covers most needs. |
| **B) Hybrid (Python + C++)** | When you need direct 2D text placement on layouts. |

## Project Structure

```
├── architecture.md              # Full design doc
├── requirements.txt
├── config/
│   ├── phases.json              # Renovation phase definitions
│   ├── sheet_conventions.json   # Sheet prefix → discipline mapping
│   ├── rules.json               # Annotation rules (condition → note)
│   └── note_templates.json      # Boilerplate note text
├── src/
│   ├── connection.py            # ACConnection wrapper
│   ├── discovery.py             # Command discovery
│   ├── models/
│   │   └── data_model.py        # Pydantic models (shared contract)
│   ├── extract/
│   │   ├── elements.py          # Read elements
│   │   ├── layouts.py           # Read navigator / layouts
│   │   ├── properties.py        # Property resolution & reading
│   │   └── renovation.py        # Renovation status mapping
│   ├── decide/
│   │   ├── phase_analyzer.py    # Phase-per-layout analysis
│   │   ├── rules_engine.py      # Rule evaluation
│   │   └── note_builder.py      # Assemble SheetNotes
│   └── apply/
│       ├── json_exporter.py     # Export SheetNotes.json
│       ├── property_writer.py   # Write to AC custom properties
│       └── text_placer.py       # (stub) Direct text placement
├── scripts/
│   ├── discover_commands.py     # Print all available AC commands
│   ├── quick_demo.py            # Minimal working example
│   └── run_annotation.py        # Full pipeline
├── tests/
│   ├── test_rules_engine.py
│   └── test_note_builder.py
├── output/                      # Generated artefacts
└── addons/
    └── layout_annotator_cpp/    # C++ Add-On (optional)
```

## Configuration

### Phases (`config/phases.json`)

Standard 3 phases: Existing, Demolition, New Construction.
Add custom phases by extending the `phases` array and adding matching rules.

### Rules (`config/rules.json`)

Each rule has a `condition` (what must be true on a layout) and a `note_section`
(which template to inject). Condition types:

- `phase_elements_on_sheet` — any elements of a given phase are present
- `phase_element_type_on_sheet` — specific element type in a phase
- `element_classification_on_sheet` — elements with a classification string

### Templates (`config/note_templates.json`)

Boilerplate text for each note section. Override per-project by editing the
templates or adding entries to `config/manual_overrides.json`.

### Manual Overrides (`config/manual_overrides.json`)

Optional per-sheet overrides:
```json
{
  "A-101": {
    "scope_notes": ["First floor demolition scope ..."],
    "manual_notes": ["Coordinate with tenant relocation"]
  }
}
```

## Testing

```bash
pytest tests/ -v
```

Tests run entirely offline using mock data — no Archicad required.

## Enabling the Archicad JSON API

1. Open Archicad 29
2. Go to **Options → Work Environment → Experimental**
   (or **Edit → Preferences** depending on OS)
3. Enable **Python / JSON API** on port **19723**
4. Restart Archicad if prompted

## License

Private / internal use.
