---
name: architectural-geometry
description: Mathematical rigor for architectural drawing geometry — coordinate systems, scale as linear transform, planar-graph face enumeration, line classification. Invoke when working on geometry extraction from PDFs, coordinate conversions, room detection, scale calibration, or any task where you need to reason about distances/areas/positions in architectural plans.
---

# Architectural Geometry Skill

Mathematical foundations for working with 2-D architectural drawings, with the discipline of a PhD in computational geometry. Apply this skill whenever the pipeline touches positions, distances, areas, or coordinate transforms.

Authoritative reference: `agent_docs/120_GEOMETRY_FRAMEWORK.md`.

---

## The three coordinate systems

A pipeline that confuses these will produce garbage. Trace every coordinate through the system it belongs to:

| System | Units | Origin | Y direction | Used by |
|---|---|---|---|---|
| **PDF user space** | points (1 pt = 1/72") | bottom-left | up | pdfplumber output |
| **Image-pixel space** | pixels | top-left | down | rendered PNG, all vision models, all HTML/SVG |
| **Real-world space** | inches | bottom-left | up | BIM tools, schedules, drafters |

Each pair is connected by one linear transform: scale + translation + Y-flip. **No rotation** in a properly drafted plan.

### Conversions (canonical)

PDF user `(px, py)` on a page of size `(page_w_pt, page_h_pt)` rendered at DPI `D`:

```
image_x_norm = px / page_w_pt
image_y_norm = (page_h_pt - py) / page_h_pt           # Y-flip
```

Image-norm `(nx, ny)` to real-world inches with calibration `inches_per_norm`:

```
real_x_in = nx * inches_per_norm
real_y_in = (1 - ny) * inches_per_norm                # Y-flip
```

These are the only formulas needed. Internalize them.

---

## Scale: the only physical constant on a sheet

Drawing scale `S` is paper-length ÷ real-length. Standard architectural set:

| Verbal | Ratio | Real-in / paper-in |
|---|---|---|
| 1/16" = 1'-0" | 1:192 | 192 |
| 1/8"  = 1'-0" | 1:96 | 96 |
| **1/4" = 1'-0"** | **1:48** | **48** ← typical floor plan |
| 1/2"  = 1'-0" | 1:24 | 24 ← enlarged plan, RCP |
| 3/4"  = 1'-0" | 1:16 | 16 ← wall section |
| 1"    = 1'-0" | 1:12 | 12 ← detail |

Never invent a non-standard scale. If a callout implies one, it's a calibration error.

### Calibration from a known dimension

When the title-block scale is unreadable, recover `S` from any visible dimension callout:

```
S = paper_distance_between_arrows / dim_value_in_inches
```

Accuracy bound is the accuracy of `paper_distance`. Ask the vision model for an explicit calibration block (text + two endpoint coords + real-world value), then derive `inches_per_norm`.

---

## A sheet is a composition, not one drawing

Critical mental model: a CD sheet typically contains **2–6 drawings + title block + legend + schedules**, each with its own scale and boundary. Pipeline must:

1. Identify the drawing-area bounding box (Claude returns it as `drawing_area_norm_bbox`).
2. Clip vector geometry to that bbox before reasoning about walls.
3. Treat title-block and schedule areas as paper-space annotations, not architectural geometry.

If you treat the whole page as one drawing, title-block lines become "walls" and the algorithm breaks.

---

## Planar-graph face enumeration

For room detection from wall segments, use Euler's formula: `V - E + F = 2` for connected planar graphs.

### Algorithm (DCEL-style)

1. **Split at intersections.** For every pair of segments crossing a third, split both at the intersection. After this no two segments cross except at shared endpoints.
2. **Snap endpoints** to a tolerance grid so vertices that should be the same collapse together.
3. **Sort half-edges by angle** at each vertex. In **image-space (Y down)** atan2 increases clockwise — so sorted order IS clockwise.
4. **Traverse faces.** For directed edge `u→v`, the next edge in the same face is the half-edge leaving `v` immediately clockwise of `v→u`. In image space that's `idx + 1` in the sorted list. (In math-space Y-up it would be `idx − 1`.)
5. **Identify the outer face** by largest absolute signed area.
6. **Filter** interior faces by **isoperimetric quotient** `4π · area / perimeter²`:
   - Rooms: IQ > 0.05 typically
   - Wall slivers: IQ < 0.05 (long-thin)

Reference: de Berg et al., *Computational Geometry* §2.2, §3.

### When face enumeration fails

If walls in the PDF aren't connected end-to-end (centerlines stop short of corners by ~half wall thickness), face enumeration finds nothing useful. Two fixes in order of preference:

1. Use the **wall edges** themselves (not paired centerlines). Inner-face wall lines DO meet at corners because that's how the architect drew them.
2. **Extend centerlines** by ~half wall thickness so they meet, then run enumeration.

If neither works, the PDF's structural signal isn't strong enough for pure geometry — fall back to the vector-hybrid path (vector walls + AI room labels snapped to walls).

---

## Line classification by stroke weight

Heavy lines = walls. Light lines = annotation. The threshold varies per PDF — measure it before assuming.

Typical ranges (in points, but treat every PDF as unique):

| Weight (pt) | Likely role |
|---|---|
| ≥ 0.70 | Cut elements in section, fire-rated assemblies, sheet borders |
| 0.50–0.69 | Walls (primary geometry) |
| 0.35–0.49 | Doors, windows, fixtures, casework, secondary architecture |
| 0.25–0.34 | Text outlines (in glyph-outlined PDFs), dimensions, hidden lines |
| ≤ 0.24 | Hatching, surface patterning, glyph fragments |

**Always** inspect the actual stroke-width histogram of a new PDF before picking a threshold. Use `pdfplumber` to enumerate `line.linewidth` and bin them.

---

## What an architect would do

Apply this filter to every geometric decision: **would a 20-year drafter measure this or guess?** If the answer is "measure," the pipeline must measure too — never substitute AI estimation for pure-geometry computation.

The only legitimate uses of AI in geometry pipelines:

1. **Semantic labels** (which polygon is the Reception, which fixture is a Toilet).
2. **Ambiguity resolution** (this paired line set might be a wall OR a casework outline — ask).
3. **Calibration** when no title-block scale is readable (find a dimension callout and report its endpoints + value).

AI never replaces pure-geometry computation for distances, positions, or areas.
