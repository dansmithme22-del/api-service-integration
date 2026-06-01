# `.claude/` — Project-local Claude infrastructure

Everything in this directory is **project-local context** for Claude
Code sessions. It's checked into the repo so the same context shows up
on any machine that clones it.

```
.claude/
├── README.md          (you are here — folder map + growth rules)
├── skills/            invocable knowledge bundles
│   ├── README.md
│   ├── team-engineering-approach.md
│   ├── architectural-geometry.md
│   ├── cad-drafting-standards.md
│   ├── csi-masterformat.md
│   ├── ibc-code-analysis.md
│   ├── bim-component-thinking.md
│   ├── architectural-vision-prompting.md
│   └── pdf-vector-extraction.md
├── personas/          team-of-specialists review lenses
│   ├── README.md
│   ├── staff-engineer.md
│   ├── dba.md
│   ├── backend-engineer.md
│   ├── frontend-engineer.md
│   └── qa-specialist.md
└── memory/            "we agreed on this" persistent context
    ├── README.md
    └── team-structure.md
```

---

## What lives in each folder

### `skills/` — knowledge bundles

A **skill** is an invocable knowledge bundle the Skill tool can load. It
describes *what to know* in a domain — the math, the standards, the API
quirks — in compact, structured form.

Each skill has YAML frontmatter with `name` + a trigger `description`.
Skills are referenced; they don't have a voice.

### `personas/` — review lenses

A **persona** is a team-member voice the Staff Engineer consults before
acting in that person's domain. Personas describe *what to flag* —
schema concerns, accessibility concerns, edge-case concerns — and carry
review checklists.

Each persona has YAML frontmatter with `name` + `role` + `domains`.
Personas are consulted; they have a voice.

### `memory/` — project-context that survives sessions

A **memory** file is a short, opinionated "we decided this and here's
why" record. Things that should be remembered across sessions but live
with the repo (not with the user across all projects).

Each memory file has YAML frontmatter with `name` + `type` + `created`.

---

## Skills vs Personas vs Memory — when to use which

| You want to… | Use |
|---|---|
| Bundle structured domain knowledge for invocation | `skills/` |
| Define a review-voice for a domain area | `personas/` |
| Record a "we agreed on this" project decision | `memory/` |
| Document technical reference (math, frameworks, APIs) | `agent_docs/` (at repo root, not here) |
| Document local design decisions for the runtime code | `agent_docs/` |

`agent_docs/` and `.claude/memory/` overlap intentionally. The split:
`agent_docs/` is **technical reference** ("how the planar-graph algorithm
works"). `.claude/memory/` is **project meta** ("how we agreed to organise
work on this codebase").

---

## How to grow each folder

### New skill

1. Create `.claude/skills/<kebab-name>.md` with the standard frontmatter.
2. Body: structured knowledge, with clear sections (when to invoke, the
   core knowledge, examples, when NOT to invoke).
3. Add a row to `skills/README.md` in the table.

### New persona

The team grows when the project hits new domains. Examples:

- **Security Engineer** — when auth ships or secrets management gets
  complex.
- **Data Engineer** — when the data pipeline gets streaming or shards.
- **SRE** — when this becomes a hosted service with uptime SLAs.
- **Design Lead** — when UI complexity grows past one review page.

To add:

1. Create `.claude/personas/<kebab-name>.md` with the standard
   frontmatter.
2. Body: principles, standing questions, review checklist, recommended
   patterns, when not to consult.
3. Add a row to `personas/README.md` in the table.
4. Add a row to the routing table in `personas/staff-engineer.md`.

### New memory

When a "we agreed on this" emerges and should survive across sessions:

1. Create `.claude/memory/<kebab-name>.md` with the standard frontmatter.
2. Body: the decision, why, how it's applied, related references.
3. Add a row to `memory/README.md` in the index.

### When a piece of memory should ALSO live at the user level

Some decisions are project-specific (live only in `.claude/memory/`).
Others should follow the user across all projects (live also in
`~/.claude/projects/-Users-danielasmith/memory/`).

The split:

| Project-only | User-wide |
|---|---|
| "This repo uses the team-of-personas pattern stored in `.claude/personas/`" | "Daniel prefers the team-of-personas approach as a default working style" |
| Specific schema versions, file conventions | General-purpose workflow preferences |
| Domain knowledge unique to this codebase | Engineering-discipline preferences |

When something belongs in both, write a project version and a user
version. Reference each other. Keep them consistent — when one
changes, update the other.

---

## Discovery / ergonomics

Claude Code surfaces skills as invocable in any session that opens this
repo. Personas and memory are not automatically loaded — they're read
when explicitly referenced (by file path in a Skill or by a session that
opens them).

To pull a persona into context mid-task, ask: "consult the DBA persona
before adopting this schema change" — that's the convention.

---

## Naming conventions

- Filenames: `kebab-case.md`.
- Frontmatter `name`: kebab-case, matches filename.
- Section headers: title case for the top, sentence case for the rest.
- Lists in tables; prose in body.
- Cross-references: relative paths (`../personas/dba.md`), not absolute.
- One concept per file. If a file gets longer than ~500 lines, split it.

---

## What's NOT in here

- **Code** — lives in `src/`, `scripts/`, `tests/` at repo root.
- **Configuration** — lives in `config/` at repo root.
- **Generated artifacts** — `ingest_output/`, `output/`, `knowledge_db/`
  are all gitignored.
- **Secrets** — never. `.env` is gitignored; the example is `.env.example`.
- **CI definition** — `.github/workflows/` at repo root.
- **Technical reference docs** — `agent_docs/` at repo root.

This folder is for working-with-Claude-on-this-project context only.
