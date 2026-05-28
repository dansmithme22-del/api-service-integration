# Vector Asset Library

Reusable vector blocks the pipeline draws into generated CD set sheets. This
is the architectural "vector" side of the knowledge stack (complementary to
the semantic embeddings DB in `src/knowledge/`).

## Layout

```
assets/
├── symbols/         Standard architectural tag symbols (SVG)
│   ├── door_tag.svg
│   ├── casework_tag.svg
│   ├── equipment_tag.svg
│   ├── column_grid.svg
│   ├── elevation_tag.svg
│   └── …
├── details/         Reusable detail blocks (SVG)
│   ├── 1hr_partition.svg
│   ├── 2hr_partition.svg
│   ├── smoke_partition.svg
│   └── …
├── typical_rooms/   Pre-laid-out standard rooms (SVG)
│   ├── exam_room_small.svg
│   ├── exam_room_large.svg
│   ├── reception.svg
│   ├── kennel_runs.svg
│   ├── treatment_island.svg
│   └── …
├── title_blocks/    Sheet title blocks (SVG)
│   ├── vetcor_title_block_a1.svg
│   └── …
└── manifest.json    Index that maps each asset to CSI division +
                    knowledge-store id for cross-referencing.
```

## Why SVG

SVG is the lingua franca:
  * Renders directly in the HTML review tool.
  * Imports cleanly into Archicad as a Drawing or into Illustrator/Affinity
    for further editing.
  * Convertible to DWG via Inkscape or qcad-cmd if a CAD-native format is
    needed downstream.
  * Source-controllable as text.

## Manifest schema

`manifest.json` maps each asset file to its place in the knowledge stack:

```json
{
  "symbols": [
    {
      "id": "sym.door_tag",
      "file": "symbols/door_tag.svg",
      "kind": "symbol",
      "csi_division": "08",
      "sheets": ["A-101", "A-601"],
      "description": "Standard door tag — letter + number inside a circle.",
      "knowledge_id": "ref:aa:abbr:DR"
    }
  ]
}
```

When the pipeline detects a tagged door on a plan, it can look up
`sym.door_tag` and stamp it into the generated drawing at the right
coordinates.

## Adding new assets

1. Draw the block in any SVG editor (Affinity, Illustrator, Inkscape).
2. Save into the appropriate subfolder.
3. Add an entry to `manifest.json`.
4. (Optional) Run `python scripts/build_knowledge_db.py --include-assets` to
   index its description in the semantic DB so AI matching works.
