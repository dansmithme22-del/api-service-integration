# Project-Local Memory

Persistent context that lives with the repo. Files here describe
**how this project works** — decisions that were made, structures
that were adopted, conventions that survive across conversations.

Different from `agent_docs/`:

- `agent_docs/` is **technical reference** — frameworks, math, APIs.
- `.claude/memory/` is **project-context** — "we decided to work this
  way; here's why; don't forget."

Different from user-level memory (`~/.claude/projects/.../memory/`):

- User memory is **across-all-projects** context that follows you.
- Project memory is **inside-this-repo** context that follows the code.

The same fact may live in both stores when it's important enough; the
two should not contradict each other.

---

## Index

| File | Topic |
|---|---|
| [team-structure.md](./team-structure.md) | The team setup — Staff Engineer + DBA + Backend + Frontend + QA — and how it's applied |

---

## How memory files are written

Memory files are short, opinionated, and act as the "we agreed on this"
record. Pattern:

```markdown
---
name: <topic>
type: project-memory
created: <YYYY-MM-DD>
---

# <Title>

## The decision

One paragraph: what we decided.

## Why

Two-three sentences: what problem this solves.

## How it's applied

Concrete: where to look, what to do, when to update.

## Related

Links to relevant skills, personas, agent_docs.
```

When a new "we agreed on this" emerges, add a file. When an old one no
longer applies, update it (don't delete — preserve the history).
