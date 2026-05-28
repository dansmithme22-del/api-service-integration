---
name: pdf-vector-extraction
description: Read architectural PDFs as CAD data — pdfplumber-based geometry extraction, stroke-weight classification, wall-pair detection, door-arc detection, text-as-outlined-paths handling. Invoke whenever the task is reading geometry from a PDF (vector or hybrid), tuning extraction thresholds, debugging why an extraction returned the wrong shapes, or building a new extraction pipeline.
---

# PDF Vector Extraction Skill

How to read a CAD-exported PDF the way a 20-year drafter would open the DWG — by inspecting the actual vector primitives, classifying them by stroke weight, and assembling them back into walls, doors, and rooms with deterministic math.

Authoritative references:
- `src/ingest/vector_anchor.py` — line-pair extraction
- `src/ingest/geometry/snap.py` — dedupe + snap + collinear merge
- `src/ingest/geometry/planar_graph.py` — face enumeration
- `src/ingest/geometry/arc_detector.py` — door swing detection
- `src/apply/svg_lossless_export.py` — lossless preservation

---

## The fundamental truth

A vector PDF exported from AutoCAD / Archicad / Revit already contains every wall, door, window, and fixture as exact vector primitives with known coordinates and stroke weights. **Do not infer geometry through AI — extract it with pdfplumber.**

The only legitimate AI step on a vector PDF is semantic labeling ("which polygon is the Reception?"). The geometry itself is in the file.

---

## Lossless extraction pipeline

```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[page_index]
    print(f"Lines:  {len(page.lines or [])}")
    print(f"Rects:  {len(page.rects or [])}")
    print(f"Curves: {len(page.curves or [])}")
    print(f"Chars:  {len(page.chars or [])}")    # 0 if text-outlined
```

Every primitive has its coordinates in PDF user space (1 pt = 1/72"). Iterate:

```python
for ln in page.lines:
    x0, y0, x1, y1 = ln["x0"], ln["y0"], ln["x1"], ln["y1"]
    width = ln.get("linewidth") or ln.get("width") or 0.0

for r in page.rects:
    # treat as 4 lines for face enumeration
    pass

for c in page.curves:
    pts = c.get("pts") or []
    width = c.get("linewidth") or 0.0
```

---

## Stroke-weight histogram (always run this first)

Before picking thresholds, enumerate the stroke widths present:

```python
from collections import Counter
widths = Counter()
for ln in page.lines:
    w = round(float(ln.get("linewidth") or ln.get("width") or 0), 3)
    widths[w] += 1
for w, c in sorted(widths.items(), key=lambda x: -x[1])[:10]:
    print(f"  width={w:.3f}pt  count={c}")
```

Typical Oly Cats output:

```
width=0.600pt  count=842    ← dominant wall stroke
width=0.240pt  count=537    ← hatching / glyph fragments
width=0.480pt  count=246    ← doors / fixtures / secondary
width=1.440pt  count=66     ← section markers
width=0.960pt  count=35     ← heavy walls
```

**The dominant stroke is the wall stroke.** Pick the threshold ABOVE the glyph noise (0.24) and AT or BELOW the wall stroke.

---

## Classification by stroke weight

```
≥ 0.70 pt → A-WALL-FIRE / section cut / sheet border / match line
0.50-0.69 pt → A-WALL-EXST / -NEWW (primary walls)
0.35-0.49 pt → A-DOOR / A-GLAZ / A-FLOR-WDWK / A-FLOR-PFIX (secondary)
0.25-0.34 pt → A-ANNO-DIMS / A-ANNO-TEXT / HIDDEN lines / fixture detail
≤ 0.24 pt → A-FLOR-PATT (hatching) or text glyph fragments
```

This is the BASELINE — every PDF has its own distribution; verify with the histogram first.

---

## Wall pair detection

Walls are drawn as two parallel close-spaced lines (the inner face + outer face). Pair detection finds them:

```python
# pseudocode — see vector_anchor.py::pair_walls_norm
for i, a in enumerate(long_lines):
    for j, b in enumerate(long_lines[i+1:]):
        # 1. same angle within angle_tol_deg (~4°)
        if abs(a.angle - b.angle) > angle_tol_deg:
            continue
        # 2. perpendicular distance within max_wall_thickness
        sep = perpendicular_distance(a, b)
        if sep > max_thickness:
            continue
        # 3. projections overlap
        if not projections_overlap(a, b):
            continue
        # found a wall pair — produce centerline + thickness
```

Tuning:

| Parameter | Typical (image-norm units at 1/4" scale) |
|---|---|
| `min_wall_len_norm` | 0.012-0.04 (= 1-4 ft real-world) |
| `pair_max_sep_norm` | 0.005-0.012 (= 8-20" real-world wall thickness) |
| `angle_tol_deg` | 1.5-4.0 |
| `min_line_width_pt` | 0.36-0.55 (per stroke-histogram) |

Tighter values → fewer false positives (cabinets won't look like walls), more false negatives (some real walls missed).

---

## Dedupe + snap + collinear merge

CAD files duplicate the same line many times (once as wall, once as hatch boundary, once as a different layer). Run this cleanup before wall pairing:

```python
from src.ingest.geometry import clean_pipeline
cleaned = clean_pipeline(
    raw_lines,
    snap_tol=0.001,      # ~ 1-3 inches at typical calibration
    angle_tol_deg=1.5,
)
```

The three stages:

1. **Dedupe** — drop lines whose endpoints (or reverse-endpoints) are within `snap_tol`.
2. **Snap endpoints** — round all endpoints to a tolerance grid so vertices that should be the same actually collapse.
3. **Merge collinear** — adjacent same-angle segments sharing an endpoint become one segment.

Typical reduction on Oly Cats: 56,897 raw → 6,492 deduped → 2,094 after merge.

---

## Planar-graph face enumeration

For room detection from wall edges (NOT centerlines — see architectural-geometry skill):

```python
from src.ingest.geometry import build_planar_graph, enumerate_faces
graph = build_planar_graph(wall_edges, snap_tol=0.0008)
faces = enumerate_faces(graph)
interior = [f for f in faces if not f.is_outer]
```

Face filtering:

```python
import math

def is_room_face(face, min_area_sf, min_iq=0.05):
    poly = face.polygon
    perim = sum(
        math.hypot(poly[(i+1) % n][0] - poly[i][0],
                   poly[(i+1) % n][1] - poly[i][1])
        for i in range(n := len(poly))
    )
    if perim < 1e-9:
        return False
    iq = (4 * math.pi * abs(face.area)) / (perim * perim)
    if iq < min_iq:
        return False           # wall sliver
    area_sf = abs(face.area) * (inches_per_norm ** 2) / 144
    return area_sf >= min_area_sf
```

The isoperimetric quotient `IQ = 4π·area / perimeter²` is a robust shape-quality metric:

- IQ = 1 → perfect circle
- IQ = π/4 ≈ 0.785 → square
- IQ = 0.05-0.30 → typical room
- IQ < 0.05 → wall sliver (long-thin)

---

## Door arc detection

Doors are drawn as a leaf line + a 90° swing arc. Curves with the right geometry are doors:

```python
from src.ingest.geometry import detect_door_arcs

door_arcs = detect_door_arcs(
    page.curves,
    min_door_width_in=24,
    max_door_width_in=48,
    sweep_min_deg=60,
    sweep_max_deg=120,
    inches_per_norm=inches_per_norm,
)
```

Filter rules:

1. Fit a circle through 3 sample points of each curve.
2. Door radius in real-world inches = door width. Typical 24-48".
3. Sweep angle ~90° (door swings open).

After detection, snap each arc center to the nearest wall endpoint — that's the hinge position.

---

## Text-as-outlined-paths handling

Many architectural PDFs export with text **converted to outlined vector paths** (especially Archicad exports). Symptoms:

```python
page.extract_text() == ""
len(page.chars) == 0
len(page.curves) >> 1000
```

The text content is gone — only the vector shapes of each letter remain. To read room names, dimensions, etc., you must:

1. Render the page to PNG.
2. OCR with a vision model (Claude / Gemini / GPT — they're better than tesseract on architectural plans).

Do NOT try to reconstruct text by pattern-matching glyph paths. That's a rabbit hole.

---

## The lossless preservation pattern

When the output deliverable must "look identical to the source PDF," preserve every primitive and emit it to SVG with original coordinates:

```python
from src.apply.svg_lossless_export import export_lossless_svg
export_lossless_svg(pdf_path, page_index=0, out_path="out.svg")
```

The exporter:

1. Reads every line, rect, and curve.
2. Classifies each by stroke weight.
3. Emits to SVG under a `<g>` for its AIA layer.
4. Preserves exact coordinates and stroke widths.
5. Renders everything in black (vector editors color by layer downstream).

This is the "replicate the PDF" baseline — accept no output that doesn't visually match the source at this stage.

---

## Common gotchas

1. **Stroke widths vary per export.** Always histogram before picking thresholds.
2. **Text outlines look like detail geometry.** They land in the medium-weight bucket. Filter them by clustering (dense small curves) or accept them as text in the lossless output.
3. **Curves are sometimes door swings, sometimes letter shapes.** Run the arc detector on curves; whatever doesn't qualify as a door arc is probably a glyph.
4. **Rects may be table cells in a schedule on the same page.** Filter by position relative to the drawing-area bbox.
5. **PDF user space is Y-up; SVG/image-norm is Y-down.** Apply the Y-flip in your conversion functions.
6. **Page coordinates are in points, not inches.** Always divide by 72.

---

## When to invoke

- Reading geometry from a new PDF for the first time
- Tuning extraction thresholds when a known-good PDF starts producing bad results
- Debugging why wall pair detection found too many / too few walls
- Adding a new geometric pattern detector (e.g. window symbols, stair patterns)
- Building a lossless replica export
- Switching from AI-derived geometry to deterministic vector extraction
