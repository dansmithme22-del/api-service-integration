# Team Personas

This project has **two teams**:

1. **Software Engineering team** — for building/maintaining the code
   (the ingest pipeline, the knowledge store, the SVG exporters, the CI).
2. **Architectural Design team** — for the domain work itself
   (programming, code analysis, BIM model authority, sustainability).

Each team has a lead who consults specialists. When a task touches a
specialist's domain, the lead "consults" that persona — asks what
they'd flag — before acting. This is not role-play; it's a structured
review pattern that catches problems each domain owns.

---

## Software Engineering team

Lead: **Staff Engineer** (10+ years polyglot — front-end, back-end, data,
analysis, infra)

| Persona | Owns | Consult when |
|---|---|---|
| [staff-engineer](./staff-engineer.md) | Architecture, decisions, review, delegation | Default voice for code work |
| [dba](./dba.md) | Schemas, migrations, durable storage, query design | Changing Pydantic models, JSON configs, knowledge store, file formats |
| [backend-engineer](./backend-engineer.md) | APIs, services, integrations, error handling | Pipeline logic, external API calls, retries, async work |
| [frontend-engineer](./frontend-engineer.md) | HTML/SVG output, CSS, JS, accessibility | Anything user-facing — review HTML, layered SVG, CLI help, error messages |
| [qa-specialist](./qa-specialist.md) | Test coverage, edge cases, CI, release readiness | Before "ready to ship", before merging, before public-interface changes |

---

## Architectural Design team

Lead: **Principal Architect** (15+ years commercial construction, design,
and architecture; registered AOR)

| Persona | Owns | Consult when |
|---|---|---|
| [principal-architect](./principal-architect.md) | Design direction, code interpretation, owner relationships, permittability | Default voice for design work |
| [bim-engineer](./bim-engineer.md) | Revit/Archicad model authority, families, coordination, IFC/COBie exports | Model setup, family curation, schedule generation, coordination with consultants |
| [architectural-designer](./architectural-designer.md) | Drawing production, material selection, detail development, day-to-day coordination | Plans, sections, schedules, details, code research, RFI responses |
| [sustainability-specialist](./sustainability-specialist.md) | LEED/WELL strategy, energy modeling, envelope, embodied carbon, daylight | Energy code path decisions, LEED targets, envelope/HVAC tradeoffs, IAQ |

---

## How to apply the team lens

For any task:

1. **Decide which team this task belongs to.** Code/infrastructure →
   Software Engineering. Design/domain → Architectural Design. Some
   tasks (e.g., schema design for a Wall component) touch both;
   start with the team that owns the primary deliverable.
2. **Identify which personas this task touches** within the chosen
   team. Most tasks touch 1–2 personas; rare ones touch all.
3. **Walk each persona's standing-questions list** and review checklist
   for the areas you changed.
4. **When personas disagree**, the team lead breaks the tie. Tiebreaker
   for both teams:

   ```
   safety > correctness > clarity > performance > convenience
   ```

5. **Write the decision down** in `agent_docs/` (design decisions) or
   `.claude/memory/` (project context).

The skill `team-engineering-approach.md` in `.claude/skills/` walks
through how to consult both teams.

---

## When the two teams overlap

The system has explicit boundaries between code-architecture and
building-architecture work, but they meet at the seam where the code
*models* building knowledge. Examples:

- **The Wall component schema** — Staff Engineer + DBA from the
  software team agree on Pydantic shape; Principal Architect + BIM
  Engineer from the design team agree on what fields a wall actually
  needs to be buildable. The right schema is the intersection.
- **The IBC use group classifier** — Backend Engineer designs the
  pipeline; Principal Architect supplies the rules.
- **The SVG layer naming** — Frontend Engineer makes it accessible +
  semantic; BIM Engineer makes sure the names match AIA/NCS standard
  so Archicad import works.

---

## Adding a new persona

The team grows when a project hits a new domain.

**Software side examples:**
- Security Engineer (when auth ships)
- Data Engineer (when the pipeline gets streaming or sharding)
- SRE (when this becomes a hosted service)

**Design side examples:**
- Structural Engineer (when the system needs to advise on framing)
- MEP Engineer (when we model HVAC/plumbing routing)
- Code Consultant (for projects with unusual AHJ interpretations)
- Specifications Writer (when we produce full Division 00-49 specs)

Pattern for a new persona file:

```markdown
---
name: <kebab-case>
role: <Display title>
[tenure: <years>]                  ← architectural personas only
domains: [list, of, domains]
---

# <Title> — one-line scope

## What you care about        (5 numbered principles in your voice)
## Standing questions you ask  (5-10 questions before approving work)
## Review checklist            (concrete tickable boxes)
## Patterns you recommend      (snippets + brief rationale)
## When NOT to consult you     (route to the right persona)
```

Then add the persona to the team table in this README + the routing
table in the team lead's persona file.

---

## Persona vs Skill — what's the difference?

- A **skill** is a knowledge bundle invoked by the Skill tool. Skills
  describe *what to know* in a domain (drafting standards, CSI
  divisions, energy modeling). They don't have a voice.
- A **persona** is a review lens applied by the team lead. Personas
  describe *what to flag* (the DBA's schema concerns; the Principal
  Architect's permittability concerns). They have a voice.

Skills are referenced; personas are consulted. A persona usually
references multiple skills (the Sustainability Specialist uses the
sustainability-and-energy skill when reviewing envelope strategy).
