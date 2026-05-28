# 80 — GLOSSARY

## Purpose

Defines Archicad-specific, architecture/interior-design, and codebase-specific terms used throughout this repository.

## When to read this

- When encountering an unfamiliar term in code, config, or documentation.
- When onboarding and needing to understand the domain vocabulary.

---

## Archicad terms

| Term | Definition |
|---|---|
| **Archicad** | BIM (Building Information Modeling) software by Graphisoft for architects and designers. |
| **JSON API** | Archicad's built-in HTTP/TCP API that accepts JSON commands on a localhost port (default 19723). Enables external automation. |
| **Python Palette** | A built-in Python code editor inside Archicad (AC 27+) for running scripts directly within the application. |
| **ACConnection** | The main connection class from the `archicad` PyPI package. Connects to a running Archicad instance. |
| **Element** | Any placed object in the Archicad model: walls, columns, slabs, doors, windows, objects, zones, etc. Each has a unique GUID. |
| **Element Type** | The category of an element: Wall, Column, Beam, Slab, Roof, Door, Window, Object, Zone, etc. |
| **GUID** | Globally Unique Identifier. Every Archicad element, layout, navigator item, and property has one. |
| **Navigator** | The tree-structured project browser in Archicad. Contains View Map, Layout Book, Publisher Sets, etc. |
| **Layout Book** | The section of the Navigator that contains all Layouts (sheets) organized in folders. |
| **Layout** | A printable sheet in Archicad (e.g., "A-101 - FIRST FLOOR PLAN"). Contains placed Drawings. |
| **Master Layout** | A template layout that defines page size, title block, and common elements. Other layouts inherit from it. |
| **Drawing** | A placed view on a Layout. A Drawing references a source View (floor plan, section, etc.) and shows its content scaled on the sheet. |
| **View** | A saved configuration for looking at the model (floor plan view, section, elevation, 3D, etc.). Views are placed as Drawings on Layouts. |
| **Renovation Status** | A property of every element indicating its phase: Existing (1), Demolition (2), or New Construction (3). |
| **Renovation Filter** | A display setting that controls which phase(s) of elements are visible in a view. |
| **Property** | A name-value pair attached to elements. Can be built-in (e.g., `General_ElementLayer`) or user-defined. |
| **Property Group** | A container for related properties (e.g., "General", "LayoutAnnotation"). |
| **Property Manager** | The Archicad dialog for creating, editing, and deleting property definitions. |
| **Classification** | A hierarchical category system for elements (e.g., "Plumbing Fixture", "Furniture"). Based on IFC or custom systems. |
| **Layer** | A visibility/organization mechanism. Elements belong to named layers (e.g., "A-Wall-Existing"). |
| **Story** | A floor level in the building (e.g., "1st Floor", "2nd Floor"). Elements are placed on stories. |
| **GDL** | Geometric Description Language. Archicad's scripting language for creating parametric library parts (objects, title blocks, etc.). |
| **GDL Object** | A parametric library part created with GDL. Can read properties via `REQUEST` and display text. |
| **AutoText** | Dynamic text fields in Archicad that auto-populate from project data (layout name, page number, custom properties). |
| **Title Block** | A GDL object on master layouts that displays project info, sheet number, revision, etc. |
| **Publisher Set** | A saved configuration for batch-publishing (printing/PDF export) layouts. |
| **Schedule** | A table that lists and totals element properties (e.g., door schedule, window schedule). |
| **Zone** | A spatial element representing a room or area. Has properties like name, number, area. |
| **Add-On** | A C++ plugin for Archicad that extends functionality using the ACAPI (Archicad C++ API). |
| **Additional JSON Commands Add-On** | A community add-on (also known as "Tapir") that adds extra JSON commands beyond the built-in set. |
| **ExecuteAddOnCommand** | A JSON API command that invokes a registered C++ Add-On command by namespace and name. |
| **ACAPI** | The Archicad C++ API used by Add-Ons. Functions like `ACAPI_Element_Create`, `ACAPI_Element_Change`. |
| **IFC** | Industry Foundation Classes. An open standard for BIM data exchange. Archicad can export/import IFC. |

---

## Architecture / interior design terms

| Term | Definition |
|---|---|
| **Sheet** | A printed drawing page. In Archicad, this corresponds to a Layout in the Layout Book. |
| **Sheet ID** | The identifying number of a sheet (e.g., "A-101"). Prefix indicates discipline. |
| **Sheet notes** | Standardized text blocks on a sheet that describe construction requirements, codes, scope, etc. |
| **Discipline** | The engineering trade a sheet belongs to: Architectural (A), Structural (S), Mechanical (M), Plumbing (P), Electrical (E), etc. |
| **Demolition plan** | A drawing showing elements to be removed during renovation. |
| **New work plan** | A drawing showing new elements being constructed. |
| **Existing conditions** | The state of the building before any renovation work. |
| **Scope of work** | A description of what construction activities are included on a particular sheet. |
| **General notes** | Standard boilerplate notes that appear on all (or most) sheets. |
| **Code notes** | Notes referencing applicable building codes (IBC, ADA, fire codes, etc.). |
| **Renovation project** | A project that modifies an existing building (vs. new construction from scratch). |
| **As-built** | Drawings that document the existing building as it was actually constructed. |
| **MEP** | Mechanical, Electrical, and Plumbing — the building systems trades. |
| **Fire-stopping** | Fire-resistant materials used to seal penetrations through fire-rated walls/floors. |
| **Rough-in** | The first stage of mechanical/plumbing/electrical installation, done before walls are closed. |

---

## Codebase-specific terms

| Term | Definition |
|---|---|
| **Extract layer** | `src/extract/` — reads data from Archicad into Pydantic models. |
| **Decide layer** | `src/decide/` — evaluates rules and builds note content. No AC dependency. |
| **Apply layer** | `src/apply/` — writes results back to AC or exports to disk. |
| **LayoutPhaseReport** | A per-layout summary of which phases are present and with which element types. Output of the phase analyzer. |
| **NoteEntry** | A single triggered note section (rule ID + section title + body text). |
| **SheetNotes** | Complete annotation payload for one layout: all notes combined. |
| **ProjectNotesOutput** | Top-level output: all SheetNotes for every layout in the project. |
| **ModelSnapshot** | Everything the Extract layer produces in one pass (elements + layouts + metadata). |
| **Property-driven approach** | Writing notes into AC custom properties → GDL object reads and displays them. |
| **JSON export approach** | Writing notes to JSON files on disk → consumed by external tools or the C++ Add-On. |
| **Conservative approach** | Attributing all elements to every layout (because per-layout filtering is not yet implemented). |
| **Rule condition** | A JSON object in `rules.json` that defines when a rule fires (phase, element type, classification). |
| **Template key** | A string that maps a rule's `note_section` to a template in `note_templates.json`. |

---

## Context-switch recap

1. **Layout** = printable sheet. **Drawing** = placed view on a layout. **View** = saved model viewing configuration.
2. **Renovation Status**: Existing (1), Demolition (2), New Construction (3) — integer codes from Archicad.
3. **Sheet ID format**: `<discipline_prefix>-<number>` (e.g., A-101 = Architectural sheet 101).
4. **Property** = name-value pair on elements. **Property Group** = container. **Property Manager** = AC dialog to manage them.
5. **GDL Object** = parametric element that can read properties and render text (used for title blocks/notes).
6. **JSON API** = localhost HTTP API on port 19723. **ACConnection** = Python SDK wrapper.
7. Three layers: Extract (read AC), Decide (rules, no AC), Apply (write back/export).
8. **NoteEntry** = one triggered note section. **SheetNotes** = all notes for one layout. **ProjectNotesOutput** = all layouts.
9. **Conservative approach** = all elements attributed to all layouts (pending per-layout filtering).
10. **Tapir** = community Add-On for extra JSON commands (optional, not required).
