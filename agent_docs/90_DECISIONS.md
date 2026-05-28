# 90 — DECISIONS

## Purpose

Documents the key architecture decisions, tradeoffs, and rationale behind the system's design. Use this as a historical record and to avoid re-debating settled decisions.

## When to read this

- When questioning why something was built a certain way.
- Before proposing a change that might conflict with an existing decision.
- When evaluating tradeoffs for a new feature.

---

## Decision 1: Three-layer architecture (Extract → Decide → Apply)

**Decision**: Separate the codebase into three independent layers with Pydantic models as the shared contract.

**Rationale**:
- **Testability**: The Decide layer has zero dependency on Archicad. All rule logic can be unit-tested with mock data.
- **Flexibility**: Each layer can be run independently. You can extract data, inspect it, then decide later whether to apply.
- **Safety**: The `--dry-run` flag and JSON export mode exist because Apply is cleanly separated.
- **Debuggability**: Intermediate artifacts (element lists, phase reports, SheetNotes JSON) can be inspected at every stage.

**Tradeoff**: More files and indirection than a single-script approach. But the modularity pays off for maintenance and testing.

---

## Decision 2: Property-driven notes (Approach A) as the recommended approach

**Decision**: Write note text into a custom Archicad property on Layout elements, then have a GDL object read and display it.

**Alternatives considered**:
| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **Property-driven** (chosen) | Survives re-publish; stable on re-open; property is persistent | Requires a GDL notes object on each master layout | **Recommended** |
| **Direct text placement** | True WYSIWYG; no GDL needed | `CreateTextElement` doesn't exist in AC 29 JSON API; requires C++ Add-On | Fallback only |
| **JSON export only** | No AC mutation; easy to version-control | Extra step to import; notes don't appear in AC automatically | Good for review/CI |

**Rationale**: The property-driven approach is the most robust and maintainable. Properties are first-class AC data, persist across file saves, and can be read by GDL via `REQUEST`. The GDL object only needs to be created once on the Master Layout.

---

## Decision 3: Pydantic for data models

**Decision**: Use Pydantic BaseModel for all data structures shared between layers.

**Rationale**:
- Type validation at construction time catches bugs early.
- `model_dump(mode="json")` provides instant JSON serialization.
- Pydantic is the most popular Python data validation library; familiar to most engineers.
- Enums (`Phase`, `Discipline`) provide type safety and IDE autocomplete.

**Tradeoff**: Adds a `pydantic>=2.0` dependency. Acceptable given the value.

---

## Decision 4: Conservative element attribution (all elements → all layouts)

**Decision**: Until per-layout element filtering is implemented, assign ALL project elements to EVERY layout when building phase reports.

**Rationale**:
- The Archicad JSON API (as of AC 29) does not provide a direct "give me the elements visible on this Drawing" command.
- Mapping Drawing → source View → Renovation Filter → visible elements requires multiple API calls and complex logic.
- The conservative approach ensures no notes are missed. It may produce some notes on sheets where they're not strictly needed, but it's safe.

**Known consequence**: Notes are identical across all sheets (e.g., demolition notes appear on every sheet, even ones that only show new work). This is explicitly documented and acceptable for MVP.

**Future fix**: Implement `layout_element_map` in `analyse_all_layouts()` by:
1. For each layout, get its placed Drawings.
2. For each Drawing, get the source View.
3. For each View, determine the Renovation Filter.
4. Filter elements by the filter's active phases.

---

## Decision 5: Wrap `archicad` SDK in `ArchicadConnection`

**Decision**: Never import the `archicad` package outside of `src/connection.py`.

**Rationale**:
- Single point of failure for connection issues.
- Easy to swap to a mock for testing (inject a mock connection object).
- Centralizes retry logic and error handling.
- `execute_raw()` provides an escape hatch for commands not wrapped by the SDK.

**Tradeoff**: Slight indirection. But the benefits far outweigh the cost.

---

## Decision 6: Config-driven rules (not code-driven)

**Decision**: Rules are defined in `config/rules.json` as data, not as Python functions.

**Rationale**:
- Non-engineers (architects, project managers) can add/edit rules by modifying JSON.
- Rules can be versioned, diffed, and reviewed alongside project files.
- The engine only needs to support a small set of condition types; new condition logic is added in code, but new rules using those conditions are config-only.

**Tradeoff**: Custom/complex conditions require adding a new evaluator function in Python. But the three existing condition types cover the majority of use cases.

---

## Decision 7: `text_placer.py` as a stub

**Decision**: Ship `text_placer.py` with attempt-and-fallback logic rather than removing it.

**Rationale**:
- Documents the intended architecture for direct text placement.
- If `CreateTextElement` becomes available in a future AC version, the integration point already exists.
- If the C++ Add-On is built and installed, the `ExecuteAddOnCommand` fallback will work without code changes.
- Better to have a documented stub than an undocumented gap.

---

## Decision 8: No `.env`, Docker, or CI

**Decision**: Keep the project as a simple local Python tool with no infrastructure.

**Rationale**:
- Target users are architects running Archicad on their local machine.
- The Archicad JSON API only accepts localhost connections — remote execution is not possible.
- Adding Docker or CI would add complexity without benefit (you can't run Archicad in Docker).
- Configuration is minimal (just a port number).

**When to reconsider**: If the tool is packaged for distribution, a `setup.py`/`pyproject.toml` would be appropriate. If running headless (e.g., a server-side process that connects to AC), Docker/CI may make sense.

---

## Decision 9: Output directory structure

**Decision**: All generated files go to `output/` with three sub-formats.

| Directory | Content | Purpose |
|---|---|---|
| `output/SheetNotes.json` | Single JSON with all sheets | Machine-readable, version-controllable |
| `output/per_sheet/<id>.json` | One JSON per sheet | For GDL objects or per-sheet consumers |
| `output/flat_text/<id>.txt` | Plain text per sheet | For pasting into AC or property injection |
| `output/available_commands.json` | API discovery dump | For debugging/reference |

**Rationale**: Different consumers need different formats. Producing all three is cheap and covers all use cases.

---

## Decision 10: Hardcoded prefix-to-discipline mapping

**Decision**: `_PREFIX_MAP` in `data_model.py` is hardcoded rather than loaded from `config/sheet_conventions.json`.

**Rationale**: Simplicity for MVP. The mapping is stable (standard AEC sheet numbering) and rarely changes.

**Known gap**: The `sheet_conventions.json` config file exists but is not dynamically loaded. This should be refactored to load from config.

---

## Open questions / future decisions needed

| Question | Context | When to decide |
|---|---|---|
| Per-layout element filtering | Currently all-to-all. Need AC API path. | When AC adds a "elements visible on Drawing" command, or when the C++ Add-On can provide this data. |
| GDL notes object template | The system assumes one exists but doesn't create it. | When deploying to a real project. Need a GDL template in the library. |
| Multi-project support | Currently single-project. | If the tool needs to operate on multiple PLN files. |
| `sheet_conventions.json` loading | Hardcoded vs. dynamic | Low priority; do when a firm uses non-standard prefixes. |
| CI pipeline | No tests in CI | If team grows or tool is distributed. |
| Versioning of output | `SheetNotes.json` has a `generated_at` timestamp but no version tracking | If output needs to be diffed over time. |

---

## Context-switch recap

1. Three-layer architecture was chosen for **testability** and **safety** (dry-run, JSON export).
2. Property-driven notes are the recommended approach; text placement is a stub/fallback.
3. Pydantic provides type safety and JSON serialization.
4. All elements → all layouts is the **conservative** approach (MVP); per-layout filtering is a known gap.
5. `ArchicadConnection` wraps the SDK so the rest of the code is mockable.
6. Rules are **config-driven** (JSON), not code-driven.
7. `text_placer.py` is intentionally a stub — it documents the integration point.
8. No Docker/CI because Archicad is localhost-only desktop software.
9. Three output formats are produced (combined JSON, per-sheet JSON, flat text).
10. `_PREFIX_MAP` is hardcoded — `sheet_conventions.json` is a documentation artifact (known gap).
