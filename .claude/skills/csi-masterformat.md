---
name: csi-masterformat
description: CSI MasterFormat 2020 — the "operating system" of construction documents. The 50-division spec organization that routes every building element to its specification section and CD-set sheet. Invoke whenever you need to classify a building element, route an item to a CD sheet, write spec section numbers, or organize project deliverables.
---

# CSI MasterFormat Skill

The CSI division code is the universal language for "which spec section does this belong to" and "which sheets should reference it." Use whenever you classify a building element or organize a project deliverable.

Authoritative reference: `config/csi_master_format.json`. Source: Construction Specifications Institute, MasterFormat 2020.

---

## The 50-division spec organization

Divisions 00-19 are general/conditions. Divisions 20-49 are technical (procurement, structure, systems). Each construction element routes to its primary division.

| Code | Name | Typical CD sheets |
|---|---|---|
| **00** | Procurement & Contracting Requirements | (front-end docs, not drawings) |
| **01** | General Requirements | G001, G002, G003 |
| **02** | Existing Conditions | AD-101, C100 |
| **03** | Concrete | S201, S301, A401 |
| **04** | Masonry | A201, A301, A401 |
| **05** | Metals | S201, S301, A401, A501 |
| **06** | Wood, Plastics, Composites | A101, A501, A901 |
| **07** | Thermal & Moisture Protection | A201, A401, A501 |
| **08** | Openings (doors, windows, hardware) | A101, A201, A501, A601, A602 |
| **09** | Finishes | A101, A603, A701, A801 |
| **10** | Specialties (signage, partitions) | A901 |
| **11** | Equipment | A901 |
| **12** | Furnishings (FFE, casework) | A901 |
| **13** | Special Construction | A901 |
| **14** | Conveying Equipment (elevators) | A101, A301 |
| **21** | Fire Suppression | FX001, FX101 |
| **22** | Plumbing | P101, P102 |
| **23** | HVAC | M101 |
| **25** | Integrated Automation | E001 |
| **26** | Electrical | E001, E101 |
| **27** | Communications | E101 |
| **28** | Electronic Safety & Security (fire alarm) | FA001, FA101 |
| **31** | Earthwork | C100, C220, C400 |
| **32** | Exterior Improvements | C200, C245 |
| **33** | Utilities | C300, C400 |

Less-common divisions (15, 16, 17, 18, 19, 20, 24, 29, 30, 34-49) are seldom used on typical projects but can be added per spec.

---

## Element-to-division quick lookup

| Element | CSI division | Layer |
|---|---|---|
| Wall (existing) | 02 — Existing Conditions | A-WALL-EXST |
| Wall (demolish) | 02 — Existing Conditions | A-WALL-DEMO |
| Wall (new framing) | 06 — Wood/Plastics or 05 — Metals (studs) | A-WALL-NEWW |
| Wall (CMU/concrete) | 04 — Masonry or 03 — Concrete | A-WALL-NEWW |
| Wall (fire-rated) | 07 — Thermal & Moisture (assembly) | A-WALL-FIRE |
| Door | 08 — Openings | A-DOOR |
| Window | 08 — Openings | A-GLAZ |
| Built-in casework | 06 — Wood, Plastics, Composites | A-FLOR-WDWK |
| Reception desk | 06 — Wood, Plastics, Composites | A-FLOR-WDWK |
| Plumbing fixture (sink, toilet) | 22 — Plumbing | A-FLOR-PFIX |
| Equipment (autoclave, X-ray) | 11 — Equipment | A-EQPM-FIXD |
| Appliance (fridge, dishwasher) | 11 — Equipment | A-EQPM-FIXD |
| Toilet partitions / accessories | 10 — Specialties | A-FLOR-SPCL |
| Movable furniture | 12 — Furnishings | A-FURN |
| Floor finish | 09 — Finishes | A-FLOR-PATT |
| Ceiling (ACT, GWB) | 09 — Finishes | A-CLNG |
| Roofing | 07 — Thermal & Moisture | A-ROOF |
| Column (steel) | 05 — Metals | A-COLS |
| Column (concrete) | 03 — Concrete | A-COLS |
| Stair (wood) | 06 — Wood | A-FLOR-STRS |
| Stair (steel) | 05 — Metals | A-FLOR-STRS |
| Stair (concrete) | 03 — Concrete | A-FLOR-STRS |
| Elevator | 14 — Conveying Equipment | A-FLOR |
| Sprinkler head | 21 — Fire Suppression | FX-101 |
| Domestic water supply | 22 — Plumbing | P-101 |
| Sanitary / vent | 22 — Plumbing | P-102 |
| HVAC duct | 23 — HVAC | M-101 |
| Power receptacle | 26 — Electrical | E-101 |
| Lighting fixture | 26 — Electrical | E-101, A-LITE |
| Data jack | 27 — Communications | E-101 |
| Fire alarm device | 28 — Electronic Safety | FA-101 |
| Site paving | 32 — Exterior Improvements | C-200 |
| Site utilities | 33 — Utilities | C-300, C-400 |

---

## CSI division → sheet routing

When building a CD set, every element belonging to a CSI division must reference one or more sheets. Use this routing:

```python
# config/cd_set.json element_routing pattern
{
  "door": {
    "csi_division": "08",
    "sheets": ["A-101", "A-501", "A-601"]
  },
  "wall_new": {
    "csi_division": "09",
    "sheets": ["A-101", "A-301", "A-401", "A-604"]
  }
}
```

The pipeline's `src/decide/scheduler.py` reads this routing to assign every detected element to its CD sheet roster.

---

## Cross-discipline coordination

A single building element often touches multiple disciplines:

- **A bathroom wall** = 09 (gypsum finish) + 22 (plumbing rough-in penetration) + 26 (electrical conduit) + 09 (tile finish) — each discipline has its own spec section.
- **A fire-rated partition** = 09 (gypsum) + 07 (penetration sealants) + 28 (smoke detection if smoke partition).

When detecting an element, assign its PRIMARY division but record any secondary coordination notes for the schedule.

---

## Spec section format

A spec section number has the form `DD NN NN`:

```
07 92 13
│  │  └─ Sub-subdivision
│  └─ Subdivision (e.g. "Joint Sealants")
└─ Division (e.g. "07 — Thermal & Moisture Protection")
```

Examples:

- `08 11 13` — Hollow Metal Doors and Frames
- `09 51 23` — Acoustical Tile Ceilings
- `22 40 00` — Plumbing Fixtures
- `26 51 00` — Interior Lighting

For permit-level CD sets, the spec book is organized by these numbers and the drawings reference the corresponding section in notes/keynotes.

---

## When to invoke this skill

- Classifying a detected element (door, wall, fixture, etc.) for scheduling
- Writing a keynote or specification reference
- Routing an element to its CD sheet(s)
- Building or editing `config/cd_set.json`
- Organizing schedule output by CSI division
- Cross-discipline coordination decisions
