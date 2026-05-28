# Geometry & Scale Framework

The rigorous account of how this pipeline maps pixels to inches and why.
Read this before debugging anything alignment-related.

---

## Context-switch recap (10 bullets)

1. A drafted sheet is a **composition**, not one drawing — multiple views,
   each with its own scale, plus title block and annotations.
2. **Three coordinate systems** are in play at all times: PDF user space,
   image-pixel space, and real-world space.
3. PDF user space uses **points** (1 pt = 1/72 inch), bottom-left origin,
   +Y up — the convention pdfplumber gives us.
4. Image-pixel space is **pixels**, top-left origin, +Y down — the
   convention all vision models and HTML/SVG use.
5. Real-world space is **inches**, bottom-left origin, +Y up — the
   convention BIM tools and architects use.
6. Each pair of systems is connected by a **linear transform**: scale +
   translation + Y-flip. There is no rotation in a properly-drafted plan.
7. **Drawing scale** (e.g. 1/4" = 1'-0") is the ratio between paper and
   real-world. It is the only physical constant on a sheet — everything
   else follows from it.
8. The pipeline can know the drawing scale by three routes: (a) explicit
   title-block text, (b) calibration from a known dimension callout,
   (c) inference from page size + assumed scale (lowest confidence).
9. **There is NO single scale for a whole sheet.** Title blocks, legends,
   schedules, and adjacent diagrams have no architectural scale at all —
   they are paper-space annotations.
10. Pipeline today assumes one scale per page. That assumption breaks
    whenever the PDF has title blocks or adjacent diagrams (which is
    nearly always).

---

## The three coordinate systems

```
   ┌─────────────────────┐    pdfplumber       ┌──────────────────────────┐
   │  PDF user space     │ ───────────────────►│  Vector path data        │
   │  pt (1/72 inch)     │                     │  in our pipeline         │
   │  origin: bottom-left│                     │                          │
   │  +X right, +Y up    │                     │                          │
   └─────────────────────┘                     └──────────────────────────┘
              │
              │ render PNG at DPI D
              ▼
   ┌─────────────────────┐    image goes to     ┌──────────────────────────┐
   │  Image-pixel space  │ ───────────────────► │  Vision model (Claude /  │
   │  pixels             │                      │  Gemini / OpenAI)        │
   │  origin: top-left   │                      │  reports image-norm      │
   │  +X right, +Y down  │                      │  coords [0, 1]           │
   └─────────────────────┘                      └──────────────────────────┘
              │
              │ × inches_per_norm
              │ Y-flip
              ▼
   ┌─────────────────────┐
   │  Real-world space   │   BIM model lives here. Schedules report
   │  inches             │   dimensions here. Builder pushes into
   │  origin: bottom-left│   Archicad here.
   │  +X right, +Y up    │
   └─────────────────────┘
```

### Conversions

For a point `(px, py)` in PDF user space on a page of size
`(page_w_pt, page_h_pt)` rendered at DPI `D`:

```
image_x_px      = px * D / 72
image_y_px      = (page_h_pt - py) * D / 72      # Y-flip

image_x_norm    = image_x_px / (page_w_pt * D / 72)  =  px / page_w_pt
image_y_norm    = image_y_px / (page_h_pt * D / 72)  =  (page_h_pt - py) / page_h_pt
```

For a point `(nx, ny)` in image-norm space on a page rendered at scale
`S` (e.g. S = 1/48 for 1/4" = 1'-0"):

```
paper_x_in      = nx * (page_w_pt / 72)
paper_y_in      = ny * (page_h_pt / 72)
real_x_in       = paper_x_in / S
real_y_in       = (1 - ny) * (page_h_pt / 72) / S       # Y-flip applied here
```

In the pipeline, we collapse `(page_in / 72) / S` into a single constant
`inches_per_norm` per page. The math becomes:

```
real_x_in       = nx * inches_per_norm
real_y_in       = (1 - ny) * inches_per_norm
```

This is the substitution that lives in `vision_parser.py::n2in()` and
`hybrid.py::_walls_from_pairs()`.

---

## Scale: the only physical constant on a sheet

Architectural drawing scale `S` is dimensionless, but always expressed
as a ratio of two lengths:

```
S  =  paper_length / real_length
```

Common values:

| Verbal | Numeric | Real-in / paper-in |
|---|---|---|
| 1/16" = 1'-0" | 1/192 | 192 |
| 1/8"  = 1'-0" | 1/96  | 96  |
| 3/16" = 1'-0" | 1/64  | 64  |
| 1/4"  = 1'-0" | 1/48  | 48  |
| 3/8"  = 1'-0" | 1/32  | 32  |
| 1/2"  = 1'-0" | 1/24  | 24  |
| 3/4"  = 1'-0" | 1/16  | 16  |
| 1"    = 1'-0" | 1/12  | 12  |

Once `S` is known, every distance on the paper can be converted to a real
distance, and vice versa. The conversion is exact. There is no
"approximate scale."

### Calibration — recovering S from a dimension

If the title-block scale is unreadable or the drawing was reproduced at
an arbitrary size, we recover `S` from any visible dimension callout:

```
S  =  paper_distance / dim_value
```

Where `paper_distance` is the measured length on paper between the two
arrowheads of the dimension line, and `dim_value` is the stated number
of inches.

The accuracy of `S` is bounded by the accuracy of `paper_distance`.
That's why we ask the vision model for an explicit calibration block
with point endpoints — the model is measuring the dimension line on the
image, and we trust those measurements.

---

## Drawing composition: one sheet ≠ one drawing

A typical CD sheet has 1–6 drawings on it. Each has:

```
┌──────────────────────────────────────────────┬─────────┐
│  ┌──────────────────────┐  ┌──────────────┐  │ Title   │
│  │ FLOOR PLAN           │  │ DOOR SCHEDULE│  │ block   │
│  │ scale 1/4" = 1'-0"   │  │ no scale     │  │         │
│  └──────────────────────┘  └──────────────┘  │ project │
│                                              │ name    │
│  ┌──────────────────────┐  ┌──────────────┐  │ date    │
│  │ WALL SECTION         │  │ ROOM FINISH  │  │ sheet # │
│  │ scale 1" = 1'-0"     │  │ SCHEDULE     │  │         │
│  └──────────────────────┘  └──────────────┘  │ legend  │
│                                              │         │
│                                              │ scale   │
│                                              │ bar     │
└──────────────────────────────────────────────┴─────────┘
```

The pipeline's ingest is currently one-page = one drawing. That is wrong
for any real CD sheet. Fix priorities:

* **Tier 1 (today's fix)**: clip vector linework to the **single drawing
  area bbox** the vision model reports. This eliminates title-block /
  legend / adjacent-view contamination for the common case of one main
  plan.
* **Tier 2**: ask the vision model for **all drawing regions** with
  their individual scales + view types. Process each independently.
* **Tier 3**: standardize a per-region `DrawingRegion` model and merge
  results by view type into a single PlanGraph that has multiple views.

---

## Why the lower-half of Oly Cats looked broken

Per the diagnosis on 2026-05-27 the data showed:

* Vector walls bbox: X[30, 985]  Y[75, 866]   inches
* Claude rooms bbox: X[90, 987]  Y[281, 907]  inches

X agrees at 93%. Y agrees only at 70%. The lower 26% of the sheet
(Y < 281 in the real-world frame, which is the **lower portion of the
PNG image**) contained vector linework that Claude did NOT label as
rooms.

That's the title-block + ancillary-diagram region. We've been treating
those as wall fragments. Fix tier 1 — clip vector geometry to Claude's
`drawing_area_norm_bbox` — removes that contamination directly.

---

## What this doc replaces

This is the geometric truth-table for everything the ingest pipeline
does. When in doubt about a coordinate, trace it through the three
systems above and check that exactly one linear transform applies
between each pair.
