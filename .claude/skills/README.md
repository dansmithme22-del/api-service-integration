# Project Skills

The professional-grade knowledge domains the architectural-automation pipeline depends on, formalized as Claude Code skills.

Each skill is invocable on its own. Each links to the deeper reference in `agent_docs/` or `config/` where the canonical data lives.

---

## The skills

### Working-process skills

| Skill | What it is | When to invoke |
|---|---|---|
| **team-engineering-approach** | The default working voice — team lead consulting specialists before acting in their domains | Starting any non-trivial task, before a design decision, before merging |

### Software-side skills

| Skill | What it is | When to invoke |
|---|---|---|
| **architectural-geometry** | PhD-level computational geometry — coordinate systems, scale as linear transform, planar-graph face enumeration | Positions, distances, areas, coordinate transforms |
| **pdf-vector-extraction** | pdfplumber-based geometry extraction — stroke classification, pair detection, arc detection | Reading PDF vector primitives, tuning extraction thresholds |
| **architectural-vision-prompting** | How to instruct vision models (Claude / Gemini / GPT) to read floor plans accurately | Writing or editing system prompts for vision-model plan analysis |
| **bim-component-thinking** | Revit-Family / SketchUp-Component schemas with build-ready properties | Designing data schemas, populating schedules, emitting BIM-tagged geometry |

### Domain / industry skills (15-year commercial expert)

| Skill | What it is | When to invoke |
|---|---|---|
| **cad-drafting-standards** | 20-year-drafter handbook — AIA Layer Guidelines, NCS, ISO 128, scales, sheet identifiers | Assigning AIA layers, picking line weights, choosing scales, numbering sheets |
| **csi-masterformat** | CSI MasterFormat 2020 — the 50-division spec/sheet routing language | Classifying elements, routing to CD sheets, writing spec sections |
| **commercial-construction** | 15-year commercial construction practice — project delivery, phases, submittals, RFIs, owner roles | Phase planning, CDs, owner conversations, reading another firm's set |
| **industrial-facility-design** | 15-year industrial perspective — warehouses, manufacturing, distribution; loading docks, racking, slabs, ventilation | Industrial use groups (F-1, F-2, S-1, S-2), process buildings |
| **architectural-design-process** | 15-year commercial AIA process — programming, SD, DD, CD, CA; contract docs; owner approval gates | Project planning, fee proposals, phase sequencing |
| **mep-mechanical-hvac** | 15-year HVAC perspective — system types, ductwork, loads, ventilation rates, controls | Mech room sizing, ductwork coordination, M-series review |
| **mep-plumbing** | 15-year plumbing perspective — fixture units, pipe sizing, hot water, IPC, backflow | Fixture counts, wet walls, hot water selection, P-series review |
| **ibc-code-analysis** | IBC 2021 — use groups, occupant loads, egress, fire ratings, accessibility | **Permit-mode only** — code sheets, egress diagrams, fire-rating callouts |
| **sustainability-and-energy** | LEED v4.1, WELL v2, IECC/ASHRAE 90.1, passive design, embodied carbon, daylight, IAQ | Energy code path, LEED targets, envelope/HVAC tradeoffs, IAQ goals |

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
