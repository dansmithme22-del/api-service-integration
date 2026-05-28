---
name: cad-drafting-standards
description: 20-year-drafter persona — AIA CAD Layer Guidelines (2nd ed.), National CAD Standard v6, ISO 128 line conventions, standard architectural scales, NCS sheet identifier format, drawing set organization. Invoke whenever the task involves assigning layer names, line types/weights, scales, sheet numbers, or organizing a drawing set.
---

# CAD Drafting Standards Skill

The seasoned drafter's reference. Apply this skill when assigning AIA layers, picking line weights, choosing scales, numbering sheets, or organizing a CD set.

Authoritative reference: `agent_docs/130_DRAFTING_STANDARDS.md`. Config files: `config/drafting/aia_layers.json`, `config/drafting/line_types.json`, `config/drafting/scales.json`, `config/drafting/sheet_types.json`.

---

## AIA / NCS Layer Format

```
D-MMMM[-NNNN][-XXXX][-STAT]
│   │      │      │      │
│   │      │      │      └─ Status: EXST | DEMO | NEWW | RELO | TEMP | FUTR
│   │      │      └─ User modifier (optional, 1-4 char)
│   │      └─ Minor group (optional, 1-4 char)
│   └─ Major group (4 char): WALL, DOOR, GLAZ, COLS, FLOR, CLNG, ROOF, AREA, ANNO, GRID, EQPM, FURN, LITE, SECT, ELEV, DETL
└─ Discipline (1 char): G H V B C L S A I Q F P D M E W T R X Z
```

### Discipline letters (memorize)

| Letter | Discipline |
|---|---|
| G | General |
| C | Civil |
| L | Landscape |
| S | Structural |
| **A** | **Architectural** |
| I | Interiors |
| F | Fire Protection |
| P | Plumbing |
| M | Mechanical (HVAC) |
| E | Electrical |
| T | Telecom |
| Q | Equipment |
| Z | Contractor / Shop |

### Canonical architectural layer set (assign-by-element)

| Element | Layer | Color | Line type | Weight (mm) |
|---|---|---|---|---|
| Walls (existing) | `A-WALL-EXST` | 8 | CONTINUOUS | 0.50 |
| Walls (demo) | `A-WALL-DEMO` | 1 | HIDDEN | 0.35 |
| Walls (new) | `A-WALL-NEWW` | 7 | CONTINUOUS | 0.50 |
| Walls (fire-rated) | `A-WALL-FIRE` | 1 | CONTINUOUS | 0.70 |
| Doors | `A-DOOR` | 4 | CONTINUOUS | 0.35 |
| Door tags | `A-DOOR-IDEN` | 4 | CONTINUOUS | 0.25 |
| Windows / glazing | `A-GLAZ` | 5 | CONTINUOUS | 0.35 |
| Columns | `A-COLS` | 7 | CONTINUOUS | 0.50 |
| Casework / millwork | `A-FLOR-WDWK` | 31 | CONTINUOUS | 0.35 |
| Plumbing fixtures (arch view) | `A-FLOR-PFIX` | 4 | CONTINUOUS | 0.35 |
| Fixed equipment | `A-EQPM-FIXD` | 3 | CONTINUOUS | 0.35 |
| Stairs | `A-FLOR-STRS` | 7 | CONTINUOUS | 0.35 |
| Room polygons / area | `A-AREA` | 7 | CONTINUOUS | 0.13 |
| Room tags | `A-FLOR-IDEN` | 7 | CONTINUOUS | 0.25 |
| Column grid | `A-GRID` | 7 | CENTER | 0.25 |
| Grid bubbles | `A-GRID-IDEN` | 7 | CONTINUOUS | 0.35 |
| Dimensions | `A-ANNO-DIMS` | 7 | CONTINUOUS | 0.25 |
| Notes / text | `A-ANNO-TEXT` | 7 | CONTINUOUS | 0.25 |
| Section / elevation tags | `A-ANNO-SYMB` | 7 | CONTINUOUS | 0.25 |
| Title block | `A-ANNO-TTLB` | 7 | CONTINUOUS | 0.50 |
| Egress paths (code) | `A-EGRS` | 1 | DASHED | 0.50 |

Color numbers are AutoCAD Color Index. Plot styles map color → weight on output.

---

## Line conventions (ISO 128)

### Weight progression

Each step is ~1.4× the previous so weights are visually distinguishable:

```
0.13 → 0.18 → 0.25 → 0.35 → 0.50 → 0.70 → 1.00 → 1.40 → 2.00 mm
```

### Standard line types

| Type | Pattern | Meaning |
|---|---|---|
| CONTINUOUS | ─────── | Visible edges; primary geometry |
| HIDDEN | ─ ─ ─ ─ | Concealed edges (overhead, below floor) |
| CENTER | ──── · ──── | Symmetry, axes, column grid |
| PHANTOM | ── ─ ─ ── | Alternate positions, adjacent objects |
| DASHDOT | ─ · ─ · ─ | Property line, match line |

### Convention specifics

- **Cut elements in sections** → 0.70 mm (heaviest of architectural set).
- **Walls in plan** → 0.50 mm.
- **Object edges beyond cut plane** → 0.35 mm.
- **Hidden objects above the cut plane** (soffits) → HIDDEN at 0.25 mm.
- **Column grid** → CENTER at 0.25 mm, bubbles at 0.35 mm.
- **Match lines** → heavy DASHDOT at 0.70 or 1.00 mm.

---

## Architectural scales

| Drawing type | Default scale |
|---|---|
| Site plan | 1" = 20', 30', 40', 50' (engineering) |
| Floor plan | **1/4" = 1'-0"** (typical), 1/8" for big plans |
| Enlarged plan (bathroom, kitchen) | 1/2" = 1'-0" |
| Reflected ceiling plan | 1/4" = 1'-0" |
| Exterior elevation | 1/4" or 1/8" = 1'-0" |
| Building section | 1/4" = 1'-0" |
| Wall section | 3/4" or 1" = 1'-0" |
| Stair section | 1/2" or 3/4" = 1'-0" |
| Plan details | 1-1/2" or 3" = 1'-0" |
| Door / window details | 1-1/2" or 3" = 1'-0" |

If the scale on the drawing is not in this set, it's wrong or non-standard. Flag it.

---

## NCS Sheet identifier

```
X-T-NNN
│ │  └─ Sequence (3 digits)
│ └─ Sheet type (1 digit)
└─ Discipline (1 char)
```

### Sheet-type digit (memorize)

| Digit | Type | Architectural examples |
|---|---|---|
| 0 | General | A-001 Cover, A-002 Code Plan, A-003 Symbols Legend |
| **1** | **Plans** | A-101 First Floor, A-102 Second Floor, A-131 RCP |
| 2 | Elevations | A-201 Exterior, A-211 Interior |
| 3 | Sections | A-301 Building, A-311 Stair |
| 4 | Large-scale views | A-401 Enlarged Plans, A-411 Wall Sections |
| 5 | Details | A-501 Door, A-511 Window, A-521 Plan Details |
| 6 | Schedules + diagrams | A-601 Door, A-611 Window, A-621 Finish |
| 7 | User defined | (firm-specific) |
| 8 | User defined | (firm-specific) |
| 9 | 3D representation | A-901 Isometric, A-911 Axonometric |

### Sequence-digit conventions

- `1xx` → first floor / level 1
- `2xx` → second floor / level 2
- `5xx` → typical details
- `6xx` → schedules
- `9xx` → 3D / FFE / specialties

---

## CD Set order (front-to-back)

```
G — General        (cover, code, symbols)
C — Civil          (site, grading, utilities)
L — Landscape      (planting, hardscape)
S — Structural     (foundations, framing)
A — Architectural  (plans, elevations, sections, details, schedules)
I — Interiors      (enlarged interiors, casework)
F — Fire Protection (sprinkler)
P — Plumbing
M — Mechanical / HVAC
E — Electrical
T — Telecom
```

---

## Title block standard fields

Right-side column or bottom edge of every sheet:

- Project name + address
- Owner
- Architect of record + seal
- Engineer(s) of record + seal
- Project number
- Drawing date + revision schedule
- Sheet title
- Sheet number
- Scale (if any)
- North arrow (if oriented)
- Key plan (for multi-area projects)

---

## Sheet sizes (ARCH series)

| Size | Dimensions | Use |
|---|---|---|
| ARCH A | 9"×12" | Pocket reference |
| ARCH B | 12"×18" | Small project |
| ARCH C | 18"×24" | Small commercial |
| **ARCH D** | **24"×36"** | **Typical CD set** |
| ARCH E | 36"×48" | Large project |
| ARCH E1 | 30"×42" | Modified ARCH E |

---

## Drafting best-practice checklist

1. **Origin first** — set drawing origin at a column-grid intersection or building corner.
2. **One element type per layer** — color BYLAYER, linetype BYLAYER, weight BYLAYER.
3. **Snap religiously** — endpoints, midpoints, intersections. Never freehand.
4. **Blocks for everything that repeats** — door swings, window symbols, plumbing fixtures, gridline bubbles.
5. **Xref upstream geometry** — arch plan into MEP; survey into site.
6. **Paper space for sheets** — model space at 1:1; viewport scale set in paper space.
7. **One dimension style per scale**.
8. **CTB or STB plot style** — pick one per firm, stick to it.
9. **Cross-references never orphan** — a callout on A-101 must land on A-301.
10. **Self-coordinate** — walls, doors, fixtures, structure, MEP all agree at every elevation.

---

## Provenance + verification

All layer names and conventions derive from AIA CAD Layer Guidelines (2nd ed.), NCS v6, and ISO 128. Verify against the official publications before using on permit-grade drawings.
