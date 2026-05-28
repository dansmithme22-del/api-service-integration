# 70 — TESTING

## Purpose

Documents the testing strategy, how to run tests, what's covered, and how to extend test coverage.

## When to read this

- Before running or writing tests.
- When adding new functionality and need to verify it.
- When CI/CD is being set up.

---

## Testing strategy

**All tests run offline** — no Archicad connection required. The test suite exercises the **Decide layer** (rules engine, phase analyzer, note builder) and the **data model** using synthetic/mock data.

The **Extract** and **Apply** layers are not unit-tested because they depend on a live Archicad connection. They are validated via integration testing (running `quick_demo.py` or `run_annotation.py` against a live AC instance).

---

## Running tests

```bash
# From repo root:
pytest tests/ -v

# With output:
pytest tests/ -v -s

# Single file:
pytest tests/test_rules_engine.py -v
pytest tests/test_note_builder.py -v
```

**Requirements**: `pytest>=7.0`, `pydantic>=2.0`. The `archicad` package is **not** needed for tests.

```bash
pip install pytest pydantic
```

---

## Test files

### `tests/test_rules_engine.py`

**Tests the rules engine** (`src/decide/rules_engine.py`) — verifying that rules fire (or don't fire) based on element data.

| Test | What it verifies |
|---|---|
| `test_demo_elements_trigger_demolition_notes` | Demolition elements → `demo_elements_present` rule fires |
| `test_no_demo_elements_no_demolition_notes` | No demolition elements → demolition rule does NOT fire |
| `test_new_walls_trigger_new_work_notes` | New Construction Walls → `new_walls_present` rule fires |
| `test_plumbing_triggers_coordination_note` | Plumbing Fixture classification → `plumbing_fixtures_present` fires |
| `test_existing_elements_trigger_existing_conditions` | Existing elements → `existing_to_remain` fires |
| `test_triggered_notes_have_body_text` | Every triggered NoteEntry has non-empty body |

**Fixtures**:
- `demo_layout` — `ACLayout(guid="test-lay-001", sheet_id="A-101", discipline=Architectural)`
- `elements_with_demo` — 3 elements (2 Demolition walls, 1 Existing wall)
- `elements_new_only` — 2 elements (1 New Wall, 1 New Column)
- `elements_with_plumbing` — 1 element (Object with classification "Plumbing Fixture")

---

### `tests/test_note_builder.py`

**Tests the note builder** (`src/decide/note_builder.py`) and the data model.

| Test class | Tests |
|---|---|
| `TestNoteBuilder` | |
| `test_build_sheet_notes_returns_model` | `build_sheet_notes()` returns a `SheetNotes` instance with correct `sheet_id` |
| `test_sheet_notes_has_general_notes` | General notes are populated from templates |
| `test_build_all_notes_covers_all_layouts` | `build_all_notes()` produces a `SheetNotes` for every layout |
| `test_flat_text_render` | `render_flat_text()` includes "GENERAL NOTES" heading |
| `test_serialises_to_json` | Full `ProjectNotesOutput` serialises to valid JSON (>100 chars) |
| `TestParseSheetId` | |
| `test_standard_prefix` | "A-101 - FIRST FLOOR PLAN" → `("A-101", Architectural)` |
| `test_plumbing` | "P-201" → `("P-201", Plumbing)` |
| `test_unknown_prefix` | "X-999" → `("X-999", Unknown)` |
| `test_non_matching` | "Some Random Name" → `(name, Unknown)` |

**Fixtures**:
- `sample_layouts` — 2 layouts (A-101, A-102)
- `sample_elements` — 4 elements (1 Demolition wall, 1 Existing wall, 1 New wall, 1 New column)

---

## What's NOT tested

| Area | Why | How to test |
|---|---|---|
| `src/connection.py` | Requires live Archicad | Integration test / mock the SDK |
| `src/extract/*` | Requires live Archicad | Run `quick_demo.py` against live AC |
| `src/apply/property_writer.py` | Requires live Archicad | Run `run_annotation.py --apply property` |
| `src/apply/text_placer.py` | Stub (no working implementation) | N/A until command exists |
| `src/apply/json_exporter.py` | File I/O | Could add unit tests for serialization |
| `src/discovery.py` | Requires live Archicad | Run `discover_commands.py` |
| Config loading | Implicitly tested via rules engine tests | Could add explicit config validation tests |

---

## Adding new tests

### For a new rule condition type

1. Create elements that should trigger the condition.
2. Create elements that should NOT trigger it.
3. Add fixtures in `test_rules_engine.py`.
4. Add test methods that call `analyse_layout()` then `evaluate_rules()` and assert the rule ID is (or isn't) in the triggered list.

### For a new template or note section

1. Add the template to `config/note_templates.json`.
2. Add a rule to `config/rules.json`.
3. Add test elements + assertions in `test_note_builder.py`.

### For the JSON exporter

```python
# Suggested test structure:
def test_export_json_creates_file(tmp_path):
    notes = ProjectNotesOutput(project_name="Test", sheets=[...])
    path = export_json(notes, output_path=tmp_path / "test.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["project_name"] == "Test"
```

---

## Integration testing (manual)

For end-to-end validation against a live Archicad instance:

```bash
# 1. Verify connection
python scripts/discover_commands.py

# 2. Run quick demo (limited element extraction)
python scripts/quick_demo.py

# 3. Full pipeline dry-run
python scripts/run_annotation.py --dry-run

# 4. Full pipeline with export
python scripts/run_annotation.py --apply json

# 5. Inspect output
cat output/SheetNotes.json | python -m json.tool | head -50

# 6. (Optional) Write properties
python scripts/run_annotation.py --apply property
# Then verify in Archicad Property Manager
```

---

## Context-switch recap

1. All tests run **offline** — no Archicad needed.
2. Two test files: `test_rules_engine.py` (6 tests) and `test_note_builder.py` (9 tests).
3. Tests cover: rule evaluation, note building, sheet ID parsing, JSON serialization.
4. Tests use synthetic `ACElement` and `ACLayout` objects as fixtures.
5. Run: `pytest tests/ -v`.
6. Extract and Apply layers need live AC for integration testing.
7. `quick_demo.py --mock` serves as an offline integration smoke test.
8. Dependencies for tests: only `pytest` and `pydantic` (no `archicad` needed).
9. Test assertions check: rule IDs in triggered list, model types, non-empty content, JSON validity.
10. No CI pipeline exists — tests are run manually.
