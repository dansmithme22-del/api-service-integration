---
name: design-team-structure
type: project-memory
created: 2026-05-28
---

# Architectural Design Team Structure

## The decision

In addition to the Software Engineering team
(see [team-structure.md](./team-structure.md)), this project also
applies an **Architectural Design team** lens whenever the work is
domain (vs code) work:

- 1× Principal Architect (lead, 15+ yr commercial AOR)
- 1× BIM Engineer (model authority)
- 1× Architectural Designer (drawing production)
- 1× Sustainability Specialist (LEED AP / energy modeling)

Personas live in `.claude/personas/`.

## Why

The project is, at its core, a system that models building knowledge.
That requires two distinct kinds of expertise that should not be
collapsed:

- **Software engineering expertise** — how to build the pipeline that
  ingests, processes, and emits the building data.
- **Architectural / construction expertise** — what the building data
  actually means; what's permittable, buildable, and worth doing.

Software engineers know how to write extraction code. They don't know
that a 1-hour corridor wall has STC implications. Architects know that
detail. The two-team structure forces both lenses on any task that
crosses the seam.

## How it's applied

For any task:

1. Identify which team owns the task. Pure code → Software. Pure
   domain knowledge → Design. Most non-trivial tasks touch both teams;
   start with the primary deliverable's owner.
2. Within the chosen team, identify which personas the task touches
   (most tasks touch 1–2).
3. Walk their "Standing questions you ask" + "Review checklist".
4. If the task crosses team boundaries (e.g., schema design for
   a building element), consult the lead from BOTH teams. The Staff
   Engineer holds the shape; the Principal Architect holds the field
   list.
5. Tiebreaker when personas disagree:
   `safety > correctness > clarity > performance > convenience`.

## Domain skills the Design team uses

Located in `.claude/skills/`:

- `commercial-construction` — project delivery, phases, CDs, submittals
- `industrial-facility-design` — F + S occupancies, docks, racking
- `architectural-design-process` — programming through CA, AIA contracts
- `mep-mechanical-hvac` — HVAC system selection, sizing, ductwork
- `mep-plumbing` — fixture units, pipe sizing, hot water, backflow
- `sustainability-and-energy` — LEED, WELL, IECC, embodied carbon
- `cad-drafting-standards` — AIA/NCS layers, scales, sheet IDs
- `csi-masterformat` — 50-division spec organization
- `ibc-code-analysis` — IBC use groups, egress, fire ratings (permit-mode)
- `bim-component-thinking` — Revit-Family/SketchUp-Component schemas

The Principal Architect references these the way the Staff Engineer
references the architectural-geometry and pdf-vector-extraction skills.

## Related

- `.claude/personas/principal-architect.md` — design lead
- `.claude/personas/bim-engineer.md`
- `.claude/personas/architectural-designer.md`
- `.claude/personas/sustainability-specialist.md`
- `.claude/personas/README.md` — both teams overview
- `.claude/skills/team-engineering-approach.md` — invocation workflow
- `.claude/memory/team-structure.md` — Software Engineering team
- User-level: `~/.claude/projects/-Users-danielasmith/memory/`
  has the cross-project default.
