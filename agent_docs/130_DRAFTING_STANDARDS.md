# Drafting Standards Handbook

The professional-drafter knowledge that should live at the core of this
pipeline. Treat this document as authoritative reference for layer naming,
line conventions, scale, sheet organization, and drawing types.

> **Provenance.** Content here is synthesized from AIA CAD Layer Guidelines
> (2nd ed.), National CAD Standard v6, ISO 128 (Technical Drawings — General
> Principles of Presentation), Autodesk AutoCAD documentation, and
> Architectural Graphic Standards (Ramsey/Sleeper). Verify against the
> official source publications before using on permit-grade drawings.

---

## Context-switch recap

1. Every element on a drawing belongs to a **layer**; layer name is
   discipline + system + subsystem + status, not arbitrary.
2. **Line weight** is the visual hierarchy. Heavier lines = primary
   geometry; lighter lines = secondary/annotation.
3. **Line type** carries semantic meaning: continuous = visible, dashed =
   hidden, center = symmetry, phantom = alternate, break = clipped.
4. **Scale** is a fixed linear transform between paper and reality.
   Architectural scales are a finite, standard set.
5. **Sheet identifier** = `discipline + sheet-type-digit + sequence`. The
   sheet-type digit is the NCS organizing key (0=general, 1=plan,
   2=elevation, 3=section, 4=enlarged, 5=detail, 6=schedule).
6. **View type** determines what's drawn: plan looks down; elevation looks
   horizontally; section is a cut through.
7. **Title block** is paper-space, not model-space, and lives in a
   reserved column or row of the sheet.
8. **Block reuse** is a hard rule — every repeating symbol (door swing,
   window tag, fixture) is a block, never freehand.
9. **External references (Xrefs)** carry shared geometry: arch plan
   xref'd into MEP, survey xref'd into site.
10. **Drawing origin** is a chosen reference (column grid intersection,
    building corner). Everything snaps to it.

---

## Layer naming — AIA / NCS format

```
   D  -  MMMM  -  NNNN  -  XXXX  -  STAT
   │       │       │        │       │
   │       │       │        │       └── Status (1-4 char, optional)
   │       │       │        └────────── User modifier (1-4 char, optional)
   │       │       └─────────────────── Minor group (1-4 char, optional)
   │       └─────────────────────────── Major group (4 char)
   └─────────────────────────────────── Discipline (1 char)
```

### Discipline codes

| Code | Discipline |
|---|---|
| `G` | General |
| `H` | Hazardous Materials |
| `V` | Survey / Mapping |
| `B` | Geotechnical |
| `C` | Civil |
| `L` | Landscape |
| `S` | Structural |
| `A` | Architectural |
| `I` | Interiors |
| `Q` | Equipment |
| `F` | Fire Protection |
| `P` | Plumbing |
| `D` | Process |
| `M` | Mechanical |
| `E` | Electrical |
| `W` | Distributed Energy |
| `T` | Telecom |
| `R` | Resource |
| `X` | Other |
| `Z` | Contractor / Shop |

### Status codes

| Code | Meaning |
|---|---|
| `EXST` | Existing to remain |
| `DEMO` | To be demolished |
| `NEWW` | New work |
| `RELO` | To be relocated |
| `TEMP` | Temporary |
| `FUTR` | Future work |
| `PHS1`, `PHS2` | Phase 1, Phase 2, etc. |

### Common architectural layers (canonical set)

| Layer | Description | Color | Line Type | Weight (mm) |
|---|---|---|---|---|
| `A-WALL` | Walls (general) | 7 (white) | CONTINUOUS | 0.50 |
| `A-WALL-EXST` | Existing walls | 8 (grey) | CONTINUOUS | 0.50 |
| `A-WALL-DEMO` | Demolished walls | 1 (red) | HIDDEN | 0.35 |
| `A-WALL-NEWW` | New walls | 7 | CONTINUOUS | 0.50 |
| `A-WALL-FIRE` | Fire-rated walls | 1 | CONTINUOUS | 0.70 |
| `A-WALL-FULL` | Full-height walls | 7 | CONTINUOUS | 0.50 |
| `A-WALL-PRHT` | Partial-height walls | 7 | CONTINUOUS | 0.35 |
| `A-WALL-PATT` | Wall hatching/patterning | 8 | CONTINUOUS | 0.13 |
| `A-DOOR` | Doors | 4 (cyan) | CONTINUOUS | 0.35 |
| `A-DOOR-IDEN` | Door tags | 4 | CONTINUOUS | 0.25 |
| `A-DOOR-FRAM` | Door frames | 4 | CONTINUOUS | 0.35 |
| `A-GLAZ` | Glazing / windows | 5 (blue) | CONTINUOUS | 0.35 |
| `A-GLAZ-IDEN` | Window tags | 5 | CONTINUOUS | 0.25 |
| `A-COLS` | Columns | 7 | CONTINUOUS | 0.50 |
| `A-FLOR` | Floor info | 7 | CONTINUOUS | 0.35 |
| `A-FLOR-FIXT` | Floor-mounted fixed equipment | 3 (green) | CONTINUOUS | 0.35 |
| `A-FLOR-WDWK` | Casework / millwork | 31 (orange) | CONTINUOUS | 0.35 |
| `A-FLOR-STRS` | Stairs | 7 | CONTINUOUS | 0.35 |
| `A-FLOR-RAIL` | Rails | 7 | CONTINUOUS | 0.25 |
| `A-FLOR-SPCL` | Specialties (toilet accessories, etc.) | 6 (magenta) | CONTINUOUS | 0.25 |
| `A-FLOR-OVHD` | Overhead features (dashed) | 7 | HIDDEN | 0.25 |
| `A-FLOR-PFIX` | Plumbing fixtures (architectural) | 4 | CONTINUOUS | 0.35 |
| `A-FURN` | Furniture (movable) | 6 | CONTINUOUS | 0.25 |
| `A-EQPM` | Equipment | 3 | CONTINUOUS | 0.35 |
| `A-EQPM-FIXD` | Fixed equipment | 3 | CONTINUOUS | 0.35 |
| `A-CLNG` | Ceiling (RCP) | 7 | CONTINUOUS | 0.35 |
| `A-CLNG-GRID` | Ceiling grid | 8 | CONTINUOUS | 0.18 |
| `A-CLNG-OPEN` | Ceiling penetrations | 7 | CONTINUOUS | 0.25 |
| `A-CLNG-SUSP` | Suspended elements | 7 | CONTINUOUS | 0.25 |
| `A-ROOF` | Roof outline | 7 | CONTINUOUS | 0.50 |
| `A-ROOF-OTLN` | Roof outline only | 7 | CONTINUOUS | 0.50 |
| `A-ROOF-CONT` | Roof contours/slopes | 7 | CENTER | 0.25 |
| `A-AREA` | Area calculations | 7 | CONTINUOUS | 0.13 |
| `A-AREA-IDEN` | Area tags | 7 | CONTINUOUS | 0.25 |
| `A-GRID` | Column grid lines | 7 | CENTER | 0.25 |
| `A-GRID-IDEN` | Grid bubbles | 7 | CONTINUOUS | 0.35 |
| `A-ANNO` | Annotations (general) | 7 | CONTINUOUS | 0.25 |
| `A-ANNO-DIMS` | Dimensions | 7 | CONTINUOUS | 0.25 |
| `A-ANNO-NOTE` | Notes | 7 | CONTINUOUS | 0.25 |
| `A-ANNO-TEXT` | Text | 7 | CONTINUOUS | 0.25 |
| `A-ANNO-SYMB` | Reference symbols (section, elevation, detail tags) | 7 | CONTINUOUS | 0.25 |
| `A-ANNO-REVS` | Revision clouds + tags | 1 | CONTINUOUS | 0.35 |
| `A-ANNO-REDL` | Redlines | 1 | CONTINUOUS | 0.35 |
| `A-ANNO-NPLT` | Non-plotting layer (construction lines, notes-to-self) | 8 | CONTINUOUS | DEFPOINTS |
| `A-ANNO-TTLB` | Title block | 7 | CONTINUOUS | 0.50 |
| `A-DETL` | Details | 7 | CONTINUOUS | 0.35 |
| `A-SECT` | Section symbols | 7 | CONTINUOUS | 0.35 |
| `A-ELEV` | Elevation symbols | 7 | CONTINUOUS | 0.35 |
| `A-LITE` | Architectural lighting (decorative) | 2 (yellow) | CONTINUOUS | 0.25 |
| `A-EGRS` | Egress paths (code plan) | 1 | DASHED | 0.50 |
| `A-CODE` | Code analysis | 7 | CONTINUOUS | 0.35 |
| `A-OCCP` | Occupant info / NSF tags | 7 | CONTINUOUS | 0.25 |

> Color numbers refer to AutoCAD Color Index (ACI). Modern practice uses
> plot-style tables (CTB) to map color → line weight when plotting.

---

## Line conventions (NCS / ISO 128)

### Line weights

| Pen weight (mm) | Use |
|---|---|
| 0.05 | Trivial detail (very fine hatching, screen tone) |
| 0.13 | Hatching, fine details, surface patterning |
| 0.18 | Minor objects, light annotation, ceiling grid |
| 0.25 | Text, dimensions, hidden lines, tags |
| 0.35 | General drawing lines, doors, windows, fixtures, casework |
| 0.50 | **Walls** and primary geometry |
| 0.70 | **Cut elements** in sections, fire-rated assemblies, sheet borders |
| 1.00 | Title block borders, match lines |
| 1.40, 2.00 | Special emphasis (rarely used) |

**Rule of thumb**: line weights step up in a 1.4× progression so they're
visually distinguishable. The set above is the ISO 128 progression.

### Line types

| Type | Pattern | Meaning |
|---|---|---|
| CONTINUOUS | ─────── | Visible edges, primary geometry |
| HIDDEN | ─ ─ ─ ─ | Concealed edges (overhead, below floor) |
| CENTER | ──── · ──── | Symmetry, axes, column grid |
| CENTER2 | ── · ── · | Tighter center pattern |
| PHANTOM | ── ─ ─ ── ─ ─ | Alternate position, adjacent objects |
| DASHED | ─ ─ ─ ─ | Generic dashed (use HIDDEN if specific meaning) |
| DASHDOT | ─ · ─ · ─ · | Property line, match line |
| BORDER | ─ ─ ── ─ ─ ── | Drawing borders |
| DIVIDE | ─ ─ · ─ ─ · | Division line |

### Convention specifics

- **Walls cut by section** are drawn with the heaviest line weight (0.70).
- **Walls in plan** are drawn at 0.50.
- **Edges of objects beyond the cut plane** drop to 0.35.
- **Hidden objects above the cut plane** (e.g. soffits) use HIDDEN at 0.25.
- **Column grid** uses CENTER at 0.25, bubbles at 0.35.
- **Match lines** are heavy DASHDOT at 0.70 or 1.00.
- **Property lines** are heavy DASHDOT at 0.70.

---

## Architectural scales

### Imperial (US standard)

| Verbal | Ratio | Real-in per paper-in |
|---|---|---|
| 1/32" = 1'-0" | 1:384 | 384 |
| 1/16" = 1'-0" | 1:192 | 192 |
| 3/32" = 1'-0" | 1:128 | 128 |
| 1/8"  = 1'-0" | 1:96  | 96  |
| 3/16" = 1'-0" | 1:64  | 64  |
| **1/4" = 1'-0"** | **1:48** | **48** |
| 3/8"  = 1'-0" | 1:32  | 32  |
| **1/2" = 1'-0"** | **1:24** | **24** |
| 3/4"  = 1'-0" | 1:16  | 16  |
| **1" = 1'-0"** | **1:12** | **12** |
| 1-1/2" = 1'-0" | 1:8 | 8 |
| 3" = 1'-0" | 1:4 | 4 |
| 6" = 1'-0" | 1:2 | 2 |
| **FULL SIZE** | **1:1** | **1** |

### Engineering / civil scales

| Verbal | Ratio |
|---|---|
| 1" = 10' | 1:120 |
| 1" = 20' | 1:240 |
| 1" = 30' | 1:360 |
| 1" = 40' | 1:480 |
| 1" = 50' | 1:600 |
| 1" = 60' | 1:720 |
| 1" = 100' | 1:1200 |

### Scale-to-drawing-type defaults

| Drawing type | Typical scale |
|---|---|
| Site plan | 1" = 20', 30', 40', 50' |
| Site demolition | 1" = 20' |
| Floor plan (small project) | 1/8" = 1'-0" |
| Floor plan (typical) | **1/4" = 1'-0"** |
| Enlarged plan (bathroom, kitchen) | 1/2" = 1'-0" |
| Reflected ceiling plan | 1/4" = 1'-0" |
| Exterior elevation | 1/4" or 1/8" = 1'-0" |
| Building section | 1/4" = 1'-0" |
| Wall section | 3/4" or 1" = 1'-0" |
| Stair section | 1/2" or 3/4" = 1'-0" |
| Door / window details | 1-1/2" or 3" = 1'-0" |
| Plan details | 1-1/2" or 3" = 1'-0" |

### Scale checking

A drawing is at the wrong scale if a 36" door is not exactly 0.75" on paper
at 1/4" = 1'-0" scale. Always verify scale by measuring a known dimension.

---

## Sheet identifier — NCS

```
   X  -  T  -  NNN
   │     │      │
   │     │      └── Sequence (3 digits)
   │     └───────── Sheet type (1 digit)
   └─────────────── Discipline (1 char)
```

### Sheet-type digit

| Digit | Type | Examples |
|---|---|---|
| `0` | General | A-001 cover, A-002 code, A-003 abbreviations |
| `1` | **Plans** | A-101 first floor, A-102 second floor |
| `2` | **Elevations** | A-201 exterior, A-211 interior |
| `3` | **Sections** | A-301 building, A-311 stair |
| `4` | **Large-scale views** | A-401 enlarged plans, A-411 wall sections |
| `5` | **Details** | A-501 door, A-511 window, A-521 plan details |
| `6` | **Schedules + diagrams** | A-601 door schedule, A-611 finish, A-621 hardware |
| `7` | User defined | (firm-specific) |
| `8` | User defined | (firm-specific) |
| `9` | 3D representation | A-901 isometric, A-911 axonometric |

### Sequence digits (NCS recommended grouping)

- 1xx: first floor / first floor variants
- 2xx: second floor / second floor variants
- 5xx: typical details
- 6xx: schedules
- 9xx: 3D / FFE / specialties

---

## Drawing set organization

### Order in a CD set

1. **G — General**: cover, sheet index, code analysis, symbol legend
2. **C — Civil**: existing conditions, site, grading, utilities, E&S
3. **L — Landscape**: planting, irrigation, hardscape
4. **S — Structural**: foundations, framing plans, sections
5. **A — Architectural**: floor plans, RCP, elevations, sections, details, schedules
6. **I — Interiors**: enlarged interiors, casework
7. **F — Fire Protection**: sprinkler
8. **P — Plumbing**: water, sanitary, vent
9. **M — Mechanical / HVAC**: ductwork, equipment
10. **E — Electrical**: power, lighting, panel schedules
11. **T — Telecom**: data/voice, low-voltage
12. **Specifications book**: separate from drawings

### Title block — standard fields

Right column or bottom edge of every sheet:
- Project name, address
- Project number
- Owner
- Architect of record + seal
- Engineer of record(s) + seal
- Issue date + revision schedule
- Sheet title
- Sheet number
- Scale (if drawing has one)
- North arrow (if drawing has orientation)
- Key plan (if multi-area project)

### Sheet sizes (ARCH series)

| Size | Dimensions | Use |
|---|---|---|
| ARCH A | 9"×12" | Pocket reference |
| ARCH B | 12"×18" | Small project |
| ARCH C | 18"×24" | Small commercial |
| **ARCH D** | **24"×36"** | **Typical CD set** |
| ARCH E | 36"×48" | Large project |
| ARCH E1 | 30"×42" | Modified ARCH E |

---

## View conventions

### Plan view

- Cut plane: 4'-0" above finished floor (AFF) — standard floor plan
  cutting plane.
- Looking DOWN.
- Anything ABOVE the cut plane is shown DASHED (HIDDEN line type).
- Anything BELOW the cut plane (floor patterning, slab edges) shown
  CONTINUOUS but lighter weight.

### Reflected ceiling plan (RCP)

- Mirror-image of the ceiling as if reflected onto the floor.
- Shows: ceiling grid, lights, diffusers, grilles, ceiling materials,
  soffits, exposed structure.
- Reads same orientation as the floor plan it pairs with.

### Elevation

- Looking HORIZONTALLY at a face of the building or a wall of an interior
  space.
- Shows: exterior cladding, openings (in elevation), grade line,
  cornice / parapet, signage.
- Interior elevations: cabinet faces, wall-mounted features, tile patterns.

### Section

- Cut plane through the building, looking perpendicular to the cut.
- Shows: vertical structure, floor-to-floor heights, ceiling heights,
  roof slopes, foundation, footings.
- Cut elements drawn HEAVIEST (0.70 mm).
- Material poché conventionally shown in cut elements.

### Detail

- Enlarged blow-up of a small condition — typically a wall section
  detail, jamb detail, sill, head, transition, corner, etc.
- Typical scales: 1-1/2" = 1'-0", 3" = 1'-0".

### Schedule

- Tabular (rows + columns), not graphic.
- Door schedule: mark, size, type, frame, hardware, fire rating
- Window schedule: mark, size, type, frame, glazing
- Room finish schedule: room, floor, base, wall, ceiling
- Equipment schedule: mark, description, manufacturer, model
- Wall type schedule: mark, composition, fire rating

---

## Block / symbol library (standard symbols)

Every well-run drafting environment maintains these as blocks:

- **Door tag** — circle, ~3/8" diameter on plan, with door # inside
- **Window tag** — hexagon, with window letter inside
- **Room tag** — name + number + area (top), grouped in a box
- **Elevation tag** — circle bisected horizontally, number above sheet number below, with arrow
- **Section tag** — same as elevation but cut indicator
- **Detail tag** — circle bisected diagonally
- **Column grid bubble** — circle with letter or number
- **North arrow** — North-pointing arrow with "N"
- **Scale bar** — graphic representation of scale
- **Match line** — heavy DASHDOT line at sheet boundaries
- **Revision cloud + delta tag** — revision callout
- **Symbol legend block** — listing every symbol on the sheet

---

## Drafting best practices (the 20-year-drafter checklist)

1. **Origin first**: Set drawing origin (0,0,0) at a column grid
   intersection or a building corner. Never start arbitrarily.
2. **Units locked in**: Inches for arch (US). Decimal precision 4 places
   minimum, 6 typical.
3. **One element type per layer**. Color BYLAYER, linetype BYLAYER, line
   weight BYLAYER. No object property overrides.
4. **Snap religiously**: All endpoints, midpoints, intersections.
   Never freehand. Never approximate.
5. **Blocks for everything that repeats**: Door swings, window symbols,
   plumbing fixtures, electrical receptacles, gridline bubbles, room tags.
6. **Xref upstream geometry**: Architectural plan as xref in MEP plans;
   survey as xref in site.
7. **Paper space for sheets**: Model space = real-world geometry at 1:1.
   Paper space = title block + viewport scaled appropriately. Annotation
   in paper space at full-size text height.
8. **One dimension style per scale**: 1/4" plan dim style differs from
   1" detail dim style.
9. **Plot style**: CTB-based (color → line weight) OR STB-based (named
   styles). Pick one per firm and stick to it.
10. **Never delete history**: Layer states, view states, named UCSs all
    preserved.
11. **Cross-references match across sheets**: A section called out on
    A-101 must exist on A-301. Never orphan callouts.
12. **Self-coordinate**: Walls, doors, fixtures, structure, MEP must all
    agree at every elevation.

---

## Application to this pipeline

When the pipeline detects an element, it should auto-assign:

- **Layer**: per AIA/NCS table above based on element type + status
- **Line type**: per layer table
- **Line weight**: per layer table
- **Color**: per layer table (ACI integer; modern practice = plot-style
  mapped)

Sheet routing already handled by CSI division mapping in
`config/cd_set.json`. The drafting standards layer is the next step
down: which AutoCAD layer / Archicad classification within that sheet
each element belongs on.

Configuration files derived from this handbook live in
`config/drafting/`:

- `aia_layers.json` — full canonical layer set
- `line_types.json` — line type / weight library
- `scales.json` — standard scales
- `sheet_types.json` — NCS sheet-type digit table

`src/knowledge/seeders.py::load_drafting()` indexes all of the above
into the semantic knowledge store so AI prompts can retrieve relevant
drafting context per query.

`config/drafting/drafter_persona.txt` is the system-prompt prefix used
when calling vision models — it loads the persona of a 20-year drafter
into the model's working context.
