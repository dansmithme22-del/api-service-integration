# Project Skills

The professional-grade knowledge domains the architectural-automation pipeline depends on, formalized as Claude Code skills.

Each skill is invocable on its own. Each links to the deeper reference in `agent_docs/` or `config/` where the canonical data lives.

---

## The skills

| Skill | What it is | When to invoke |
|---|---|---|
| **team-engineering-approach** | The default working voice — Staff Engineer leading a small team (DBA, Backend, Frontend, QA), consulting each persona before acting in their domain | Starting any non-trivial task, before a design decision, before merging work |
| **architectural-geometry** | PhD-level computational geometry for plans — coordinate systems, scale as linear transform, planar-graph face enumeration | Anything touching positions, distances, areas, or coordinate transforms |
| **cad-drafting-standards** | 20-year-drafter persona — AIA Layer Guidelines, NCS, ISO 128, scales, sheet identifiers | Assigning AIA layers, picking line weights, choosing scales, numbering sheets |
| **csi-masterformat** | CSI MasterFormat 2020 — the 50-division spec/sheet routing language | Classifying a building element, routing to CD sheets, writing spec sections |
| **ibc-code-analysis** | IBC 2021 — use groups, occupant loads, egress, fire ratings, accessibility | **Permit-mode only** — code analysis sheets, egress diagrams, fire-rating callouts |
| **bim-component-thinking** | Revit-Family / SketchUp-Component schemas — walls, doors, windows, floors, ceilings, stairs, decks with build-ready properties | Designing data schemas, populating schedules, emitting BIM-tagged geometry |
| **architectural-vision-prompting** | How to instruct vision models (Claude / Gemini / GPT) to read floor plans accurately | Writing or editing system prompts for vision-model plan analysis |
| **pdf-vector-extraction** | pdfplumber-based geometry extraction — stroke classification, pair detection, planar graphs, arc detection | Reading a PDF's vector primitives, tuning extraction thresholds, building lossless replicas |

---

## How they layer

```
                        ┌─────────────────────────┐
                        │  bim-component-thinking │   ← top: how to STRUCTURE output
                        └────────────┬────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────▼──────────┐ ┌─────────▼──────────┐ ┌─────────▼─────────────┐
   │ csi-masterformat    │ │ cad-drafting-      │ │ ibc-code-analysis     │
   │ (routing logic)     │ │ standards          │ │ (permit-mode only)    │
   │                     │ │ (AIA/NCS/ISO 128)  │ │                       │
   └─────────────────────┘ └────────────────────┘ └───────────────────────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
                        ┌────────────▼──────────────┐
                        │  architectural-geometry   │   ← mid: the MATH
                        │  (coordinates, scale,     │
                        │   planar graphs)          │
                        └────────────┬──────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                                             │
 ┌────────────▼──────────────┐               ┌──────────────▼─────────────┐
 │ pdf-vector-extraction     │               │ architectural-vision-      │
 │ (deterministic, no AI)    │               │ prompting                  │
 │ pdfplumber, stroke-weight │               │ (vision models for         │
 │ classification            │               │  semantic labels)          │
 └───────────────────────────┘               └────────────────────────────┘
```

- **Bottom row**: the two input paths into the pipeline — deterministic vector extraction (left) and AI semantic labeling (right).
- **Middle**: the mathematical framework that connects them and keeps coordinate systems straight.
- **Upper rows**: the standards (drafting, CSI, IBC) that classify what we extracted, and the component schemas that structure the output.

A typical pipeline run touches every skill at least once.

---

## Provenance + verification

The drafting / CSI / IBC content in these skills is synthesized from published industry standards (AIA CAD Layer Guidelines 2nd ed., NCS v6, CSI MasterFormat 2020, IBC 2021, ISO 128, Architectural Graphic Standards). For permit-grade or contract-grade work, **always verify against the official publications and any local amendments before output goes in front of a code official or contractor**.

The computational-geometry content (planar graphs, face enumeration, isoperimetric quotient) is standard material from de Berg et al., *Computational Geometry* (3rd ed.) and equivalent references.

---

## Related references in the repo

| Skill | Deep reference |
|---|---|
| architectural-geometry | `agent_docs/120_GEOMETRY_FRAMEWORK.md` |
| cad-drafting-standards | `agent_docs/130_DRAFTING_STANDARDS.md` + `config/drafting/` |
| csi-masterformat | `config/csi_master_format.json` + `config/cd_set.json` |
| ibc-code-analysis | `config/ibc_use_groups.json` |
| bim-component-thinking | `src/components/schemas.py` |
| architectural-vision-prompting | `src/ingest/vision_parser.py::SYSTEM_PROMPT` + `config/drafting/drafter_persona.txt` |
| pdf-vector-extraction | `src/ingest/vector_anchor.py` + `src/ingest/geometry/` |
