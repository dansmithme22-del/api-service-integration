---
name: bim-component-thinking
description: Revit-Family / SketchUp-Component way of thinking — every building element is an atomic unit with a complete property set defining how to actually build or specify the item. Invoke when designing data schemas for walls/doors/windows/floors/ceilings/stairs/decks, or when emitting BIM-tagged drawing output, or when populating schedules.
---

# BIM Component Thinking Skill

A component is an indivisible building element with **everything someone needs to actually build or specify the item**. Use this skill when defining schemas, populating schedules, or emitting BIM-tagged geometry.

Authoritative reference: `src/components/schemas.py`. Mental model: Revit Families and SketchUp Components — every property a tradesperson, estimator, or specifier needs in one bundle.

---

## The seven baseline component kinds

| Kind | Primary CSI | Primary AIA layer |
|---|---|---|
| **Wall** | 02 / 09 (status-dependent) | A-WALL-EXST / -DEMO / -NEWW |
| **Door** | 08 | A-DOOR |
| **Window** | 08 | A-GLAZ |
| **Floor** | 09 | A-FLOR |
| **Ceiling** | 09 | A-CLNG |
| **Stair** | 06 | A-FLOR-STRS |
| **Deck** | 06 | A-FLOR |

Every component on a plan should map to exactly one of these (or its variants).

---

## Universal component fields

All components carry these regardless of kind:

```
id              unique identifier
mark            schedule mark (W001, D012, R005, FL001, ...)
kind            Wall | Door | Window | Floor | Ceiling | Stair | Deck
name            human display name ("Interior Stud Wall 2x6")
aia_layer       AIA/NCS layer name
csi_division    CSI division code
sheets          list of CD sheet codes the component appears on
notes           free-form notes
geometry        list of SVG-paintable primitives (lines, polygons, arcs)
extras          dict for project-specific or manufacturer fields
```

The component's `data-properties` JSON in the SVG should be a flat dump of every field below (kind-specific block included).

---

## Wall — what to record

```
start, end                  centerline endpoints (real-world inches)
thickness_in                from face to face
height_in                   floor-to-deck or floor-to-ceiling
length_in                   derived from start/end if not set
wall_type                   "Interior Stud" | "Exterior Stud" | "CMU" | "Concrete" | "Demising"
composition                 ordered list of AssemblyLayer (side A → side B)
structural                  bool
load_bearing                bool
fire_rating                 "" | "1HR" | "2HR" | "3HR" | "4HR"
sound_rating_stc            int (50 typical for demising; 0 = unrated)
insulation_r_value          float (R-value)
finish_side_a               "GWB Painted" | "Tile" | "Wood Paneling" | ...
finish_side_b               same
base_side_a                 "Rubber Cove 4\"" | "Wood Base" | ...
base_side_b                 same
status                      "Existing" | "Demolition" | "New Construction"
code_references             list of IBC/IRC section citations
```

### Wall composition pattern (interior stud)

```
- GWB 5/8" Type X (Side A)        finish, 0.625"
- Steel Stud 3-5/8" @ 16" o.c.    substrate, 3.625"
- GWB 5/8" Type X (Side B)        finish, 0.625"
                                  Total: 4.875" (≈ 4-7/8")
```

### Wall composition pattern (exterior stud, R-21)

```
- GWB 5/8" Type X (Interior)            finish, 0.625"
- Steel Stud 6" @ 16" o.c.              substrate, 6.0"
- Mineral Wool R-21                     insulation, 6.0"
- Exterior Sheathing 5/8" Gypsum        substrate, 0.625"
- Air & Water Barrier (WRB)             vapor/air barrier, 0.05"
- Continuous Insulation R-10            insulation, 2.0"
- Metal Panel Cladding                  finish, 0.75"
                                        Total: ~16" wall depth
```

---

## Door — what to record

```
position                    center on host wall (real-world coords)
host_wall_id                wall this door is in
width_in, height_in         door leaf dimensions
leaf_thickness_in           typical 1.75"
door_type                   "Single Swing" | "Double Swing" | "Sliding"
                            | "Pocket" | "Folding" | "Overhead"
swing_direction             "LHR" | "RHR" | "LH" | "RH" (IBC convention)
operation                   "Active" | "Inactive" | "Both"
leaf_material               "Solid Core Wood" | "Hollow Metal" | "Aluminum"
                            | "FRP" | "Glass"
leaf_finish                 product spec (stain, paint, etc.)
frame_material              "Hollow Metal" | "Wood" | "Aluminum"
frame_finish, frame_profile
hardware_set                "HW-1", "HW-2", ... (cross-ref to hardware schedule)
lockset_type                "Lever Latch" | "Mortise" | "Cylinder Knob" | "Push/Pull"
closer                      bool
threshold                   bool
weatherstripping            bool
kick_plate                  "" | "10\" Stainless Steel" | ...
fire_rating                 "" | "20-min" | "45-min" | "60-min" | "90-min" | "3HR"
smoke_rated                 bool
acoustic_rating_stc         int
has_vision_panel            bool
vision_panel_size           "" | "12x36" | ...
glazing_type                "" | "Tempered" | "Wired" | "Laminated"
ada_compliant               bool
clear_opening_width_in      32" minimum for ADA
threshold_height_in         <= 0.5" for ADA
```

---

## Window — what to record

```
position                            center on host wall
host_wall_id
rough_opening_width_in
rough_opening_height_in
sill_height_in                      30" typical residential, 24" typical commercial
window_type                         "Fixed" | "Double-Hung" | "Single-Hung"
                                    | "Casement" | "Awning" | "Sliding" | "Picture"
operable                            bool
n_lites                             1 = single glazed; 2 = IGU; 3 = triple
grille_pattern                      "" | "Colonial 2x2" | ...

# Glazing details
glazing_type                        "IGU" | "Single" | "Laminated" | "Tempered"
glass_thickness_in                  total for IGU
inner_pane_thickness_in
outer_pane_thickness_in
gas_fill                            "Air" | "Argon" | "Krypton"
low_e_coating                       "" | "Low-E 366" | "Low-E 272" | ...

# Performance
u_factor                            Btu/hr·ft²·°F (lower = better)
shgc                                Solar Heat Gain Coefficient (0-1)
vt                                  Visible Transmittance (0-1)

# Frame
frame_material                      "Aluminum, Thermally Broken" | "Wood Clad"
                                    | "Vinyl" | "Fiberglass"
frame_finish, frame_color
frame_thickness_in
sill_material
head_trim

# Code
egress_qualified                    bool (size minimums for emergency egress)
impact_rated                        bool (hurricane / projectile)
safety_glazing_required             bool (if within 24" of door, < 60" AFF, etc.)
```

---

## Floor — what to record

```
polygon                             real-world inch coordinates
area_sqft
floor_type                          "Slab on Grade" | "Wood Framed" | "Steel Framed"
                                    | "Concrete Suspended"
structure_depth_in                  slab thickness or joist depth
joist_size                          "" | "2x10" | "I-Joist 11-7/8" | ...
joist_spacing_in                    0 if slab; 16/19.2/24 if framed
joist_span_in                       horizontal span; checked against allowable per IRC

composition                         layer list top → substrate
finish_top                          "LVT" | "Tile" | "Carpet" | "Wood"
                                    | "Polished Concrete" | "Epoxy"
finish_thickness_in

# Performance
moisture_barrier                    bool
insulation_r_value                  float
sound_rating_iic                    impact sound (50 typical apt above apt)
sound_rating_stc                    airborne sound
radiant_heat                        bool
```

### Floor composition example (slab on grade)

```
- LVT, 0.125"                       finish
- Underlayment Foam, 0.125"         substrate
- Concrete Slab, 4"                 structure
- Vapor Barrier (poly), 0.05"       vapor barrier
- Compacted Gravel, 4"              substrate
                                    Total: ~8.3"
```

---

## Ceiling — what to record

```
polygon, area_sqft
ceiling_type                        "ACT 2x2" | "ACT 2x4" | "GWB Painted"
                                    | "Open Structure" | "Wood Plank" | "Metal"
height_in                           AFF (above finished floor)
finish                              "Tegular ACT, White" | "GWB, Painted Eggshell"
composition                         layer list
grid_size                           for ACT only
support                             "Suspended Wire" | "Direct Hung" | "None (Open)"
plenum_depth_in                     gap between ceiling and structure above
fire_rating                         "" | "1HR" | ...
sound_absorption_nrc                NRC (0-1, higher = more absorptive)
light_reflectance                   0-1 (0.85 standard for white ACT)
```

---

## Stair — what to record

```
polygon, run_in, width_in
stair_type                          "Straight" | "L-Shape" | "U-Shape"
                                    | "Switchback" | "Spiral"
total_rise_in                       floor-to-floor (typically 108" for 9' ceiling)
num_risers                          riser count
riser_height_in                     IBC max 7.75" residential, 7" commercial
num_treads                          always num_risers - 1
tread_depth_in                      IBC min 10" residential, 11" commercial
nosing_in                           IBC max 1.25" projection
landing_count                       intermediate landings

# Materials
tread_material, riser_material      "Concrete" | "Wood" | "Steel Grate"
stringer_material                   for open stairs
handrail_material                   "Steel, Painted" | "Wood, Stained"

# Railings (IBC §1011, §1015)
handrail_height_in                  34-38" per IBC 1014.2
guardrail_height_in                 42" if change in elevation > 30"
baluster_spacing_in                 < 4" sphere (IBC §1015.4)
```

---

## Deck — what to record

```
polygon, area_sqft
deck_type                           "Wood Frame" | "Steel Frame" | "Concrete"

# Structure
joist_size                          "2x8" | "2x10" | "2x12"
joist_spacing_in                    16 typical
joist_span_in                       check IRC Table R507.6
beam_size                           "(2) 2x10" | ...
post_size                           "6x6" minimum for elevated decks
post_spacing_in                     typically 96" max

# Surface
decking_material                    "Composite" | "Pressure Treated Wood"
                                    | "Ipe" | "Cedar"
decking_thickness_in                1" min for composite
decking_pattern                     "Parallel to Long Edge" | "Diagonal" | "Picture Frame"

# Railings
guardrail_height_in                 36" min (42" if > 30" above grade)
baluster_spacing_in                 < 4" sphere
railing_material

# Waterproofing
waterproof_membrane                 for elevated decks over occupied space
drainage_slope_percent              typically 1-2%

# Building connection (IRC R507)
ledger_size                         matched to joist size
ledger_attachment                   "Lag Bolts to Rim Joist" | "Through-Bolts" | "Bracket"
flashing                            "Aluminum Step Flashing" | "Membrane"
```

---

## Component invariants

These rules MUST hold for every emitted component:

1. **Geometry is self-contained.** Every line/curve/polygon that draws the component belongs to its `<g>`, not a sibling.
2. **Properties tell you how to build it.** A reader should be able to spec the item from `data-properties` alone.
3. **Mark cross-references the schedule.** `data-mark` matches the schedule row mark exactly.
4. **CSI division is set.** Every component has a primary division.
5. **AIA layer is set.** Every component has its AIA/NCS layer.
6. **Status is set for renovation work.** Every wall has Existing | Demolition | New Construction.
7. **No text glyph noise.** Outlined text in the source PDF is NOT a component. Drop it.

---

## When to invoke

- Designing data schemas for new element types
- Writing schedule output (door, window, wall, finish, equipment schedules)
- Emitting BIM-tagged SVG / PDF
- Populating Archicad or Revit via API
- Generating spec section content from the model
- Producing takeoff / quantity surveys
