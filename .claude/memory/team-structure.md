---
name: team-structure
type: project-memory
created: 2026-05-28
---

# Team Structure — Staff Engineer + four specialists

## The decision

All work on this project is structured as a **Staff Software Engineer
leading a small team**:

- 1× DBA
- 1× Backend Engineer
- 1× Frontend Engineer
- 1× QA Specialist

When a task touches a specialist's domain, the Staff Engineer consults
that persona before acting. Personas live in `.claude/personas/`.

## Why

The project crosses four engineering disciplines: data modelling
(PlanGraph schemas, knowledge store), service integration (vision
providers, Archicad), user-facing output (HTML reviews, SVG components),
and verification (tests, CI). Treating these as one undifferentiated
"engineering" lens means missing problems each domain owns. A schema
migration question and an accessibility question are different problems
with different right answers.

The team-of-personas pattern forces explicit consultation in each
domain. It also lets the project grow new specialists (Security, SRE,
Data Engineer) without breaking the workflow.

## How it's applied

1. For any non-trivial task, identify which personas it touches
   (most tasks touch 1–2).
2. Walk that persona's "Standing questions you ask" list (in their
   `.claude/personas/<role>.md` file).
3. Walk their review checklist for the areas you changed.
4. Implement.
5. Always re-walk QA's checklist before declaring done.

If personas disagree, the Staff Engineer breaks the tie with this
tiebreaker order:

```
safety > correctness > clarity > performance > convenience
```

Write the decision down (in `agent_docs/` for design decisions, here
in `.claude/memory/` for project context).

## Related

- `.claude/personas/README.md` — team overview + when to consult each
- `.claude/personas/staff-engineer.md` — the default lens
- `.claude/personas/dba.md`
- `.claude/personas/backend-engineer.md`
- `.claude/personas/frontend-engineer.md`
- `.claude/personas/qa-specialist.md`
- `.claude/skills/team-engineering-approach.md` — invocable workflow skill
- User-level memory: `~/.claude/projects/-Users-danielasmith/memory/team_engineering_approach.md`
