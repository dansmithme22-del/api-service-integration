# 00 — START HERE

## Purpose

Single entry point for any engineer or LLM agent working on this repository for the first time. Tells you **what the project does**, **where to look**, and **how to orient yourself** in under 5 minutes.

## When to read this

- **Always first.** Before any other agent_docs file or before modifying any code.
- During a context-switch when you need to regain situational awareness.

---

## What this repo does (one paragraph)

This is a **Layout Annotation Automation** system for **Archicad 29**. It connects to a running Archicad instance via the JSON/Python API, reads model elements and their renovation phases, evaluates configurable rules, and generates per-sheet construction notes (demolition notes, new-work notes, code notes, etc.). The output can be exported as JSON files or written directly into Archicad custom properties on Layout elements so that a GDL title-block object can display them on printed sheets.

## Who uses it

Architects and interior designers working in Archicad on renovation projects. The system automates the tedious process of writing and maintaining sheet notes that vary per layout based on what's being demolished, built new, or remaining.

---

## Repo map (quick reference)

| Path | What it is |
|---|---|
| `src/connection.py` | Wrapper around `archicad.ACConnection` — the single point of contact with Archicad |
| `src/discovery.py` | Enumerates every JSON command the running AC instance exposes |
| `src/extract/` | **Layer 1**: Reads elements, layouts, properties, renovation status from AC |
| `src/decide/` | **Layer 2**: Rules engine + phase analysis → produces `SheetNotes` models |
| `src/apply/` | **Layer 3**: Writes results back (JSON export, property write, text placement stub) |
| `src/models/data_model.py` | Pydantic data models — the shared contract between all layers |
| `config/` | JSON config files: rules, templates, phases, sheet conventions |
| `scripts/` | CLI entry points: `run_annotation.py`, `quick_demo.py`, `discover_commands.py` |
| `tests/` | Offline pytest tests (no Archicad needed) |
| `output/` | Generated artefacts (`SheetNotes.json`, per-sheet files, flat text) |
| `addons/layout_annotator_cpp/` | Optional C++ Add-On for direct text placement (skeleton) |
| `architecture.md` | Full design document with diagrams |

---

## Key concepts to know

1. **Three-layer pipeline**: `EXTRACT → DECIDE → APPLY` — every workflow follows this.
2. **Renovation phases**: Archicad elements have a status: Existing (1), Demolition (2), New Construction (3). Rules fire based on which phases are present on a sheet.
3. **Rules engine**: `config/rules.json` defines conditions; `config/note_templates.json` defines boilerplate text. A rule = "if condition X is true on this layout, inject template Y."
4. **Two apply strategies**: (a) JSON export to `output/` (safe, no AC mutation), (b) write to a custom Archicad property `LayoutAnnotation_SheetNotesText` (requires a GDL object to render).
5. **Connection**: Uses the `archicad` PyPI package → `ACConnection.connect(port)` → sends JSON commands over TCP to `127.0.0.1:<port>`.

---

## How to run (30-second quickstart)

```bash
pip install -r requirements.txt

# No Archicad needed:
python scripts/quick_demo.py --mock

# With Archicad running:
python scripts/run_annotation.py --port 19723 --apply json
```

---

## Navigation to other agent_docs

| File | Read when you need to… |
|---|---|
| [10_ARCHITECTURE.md](10_ARCHITECTURE.md) | Understand the three-layer design, data flow, and module responsibilities |
| [20_WORKFLOWS.md](20_WORKFLOWS.md) | Trace any end-to-end workflow step by step |
| [30_ARCHICAD_INTEGRATION.md](30_ARCHICAD_INTEGRATION.md) | Connect to / operate against a live Archicad instance |
| [40_CODE_TO_ARCHICAD_MAP.md](40_CODE_TO_ARCHICAD_MAP.md) | Map code modules to Archicad concepts (Layouts, Properties, Renovation, etc.) |
| [50_CONFIG_AND_SECRETS.md](50_CONFIG_AND_SECRETS.md) | Understand or modify config files |
| [60_TROUBLESHOOTING.md](60_TROUBLESHOOTING.md) | Debug connection failures, missing properties, or unexpected output |
| [70_TESTING.md](70_TESTING.md) | Run or extend tests |
| [80_GLOSSARY.md](80_GLOSSARY.md) | Look up Archicad or domain-specific terms |
| [90_DECISIONS.md](90_DECISIONS.md) | Understand why something was built a certain way |

---

## Context-switch recap (for LLM agents)

1. This is a **Python automation tool for Archicad 29** (BIM software for architects).
2. Pipeline: **Extract** (read model from AC API) → **Decide** (evaluate rules, build notes) → **Apply** (export JSON or write properties).
3. Entry point: `scripts/run_annotation.py` — connects on port 19723 by default.
4. Data contract: Pydantic models in `src/models/data_model.py` — `ACElement`, `ACLayout`, `SheetNotes`, `ProjectNotesOutput`.
5. Rules are in `config/rules.json`; note text templates in `config/note_templates.json`.
6. Tests run offline: `pytest tests/ -v` — no Archicad needed.
7. Two apply modes: `--apply json` (file export) and `--apply property` (write to AC).
8. The `text_placer.py` module is a **stub** — direct text placement requires a C++ Add-On.
9. Connection wrapper: `src/connection.py` → `ArchicadConnection` class wraps `archicad.ACConnection`.
10. No `.env`, no Docker, no CI — it's a local-first tool run from terminal or Archicad's Python Palette.
