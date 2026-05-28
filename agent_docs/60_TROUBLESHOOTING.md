# 60 — TROUBLESHOOTING

## Purpose

Diagnose and fix common errors. Organized by symptom so you can search for what you're seeing.

## When to read this

- When a script fails or produces unexpected output.
- When the connection to Archicad drops or refuses.
- When notes are missing, wrong, or empty.

---

## Connection errors

### `ImportError: The 'archicad' package is not installed`

**Cause**: The `archicad` PyPI package is not in the current Python environment.

**Fix**:
```bash
pip install archicad
# or
pip install -r requirements.txt
```

If running from Archicad's Python Palette, install into the palette's environment:
```python
import subprocess
subprocess.check_call(["pip", "install", "archicad"])
```

---

### `ConnectionError` / `ConnectionRefusedError` when connecting

**Cause**: Archicad is not running, or the JSON API is not enabled, or the port is wrong.

**Checklist**:
1. Is Archicad 29 running?
2. Is the JSON/Python API enabled? (Settings → Work Environment → Experimental)
3. Is a project file open? (Some commands fail without an open project.)
4. Is the port correct? Default is `19723`. Check with `--port`.
5. Is another process using port 19723?

**Quick test**:
```bash
curl -X POST http://127.0.0.1:19723 \
  -H "Content-Type: application/json" \
  -d '{"command": "IsAlive"}'
```

---

### `RuntimeError: Not connected to Archicad. Call .connect() first.`

**Cause**: Code is trying to use `conn.commands` / `conn.types` before calling `conn.connect()`.

**Fix**: Ensure `ArchicadConnection(port).connect()` is called before any operations. All three scripts handle this automatically.

---

## Extract errors

### `GetAllElements returned 0 elements`

**Possible causes**:
- The project is empty (no elements placed).
- The project file is not fully loaded yet. Wait for Archicad to finish opening.
- The API connection is stale. Try reconnecting.

---

### `Could not build ElementId objects; returning basic models`

**Cause**: The SDK's `types.ElementId` constructor failed. May be a version mismatch.

**Fix**: Check that your `archicad` package version matches your Archicad version:
```bash
pip show archicad
```
Install the version matching your AC: e.g., `pip install archicad==29.*`.

---

### `GetPropertyValuesOfElements failed`

**Cause**: One or more property IDs are invalid, or the element IDs are stale.

**Debugging**:
1. Run `scripts/discover_commands.py` to verify the API is responsive.
2. Check logs for "Could not resolve property" warnings — indicates a property name mismatch.
3. The property names use the convention `Group_Name` (e.g., `General_RenovationStatus`). Verify these exist in your project's Property Manager.

---

### `No layouts found in the Layout Book`

**Cause**: The project has no layouts, or the LayoutBook navigator tree has a different structure.

**Fix**:
1. Open Archicad's Navigator → Layout Book.
2. Verify at least one Layout exists (not just folders).
3. If layouts exist but aren't found, check the logs for "Retrieved generic navigator tree" or "Could not retrieve navigator tree" — may indicate an SDK version difference.

---

## Decide errors

### Rules not firing (no element_driven_notes in output)

**Cause**: Either no elements match the rule conditions, or the condition type is unknown.

**Debugging**:
1. Check `output/SheetNotes.json` — look at `element_driven_notes` array per sheet.
2. Run with `--dry-run` to inspect the full output.
3. Check logs for "Unknown condition type" — indicates a rule has a `condition.type` not registered in `_EVALUATORS`.
4. Check logs for "Rule X fired for sheet Y" — appears at DEBUG level. Run with `logging.DEBUG` to see.
5. **Important**: Currently, ALL elements are attributed to EVERY layout (conservative approach). So if any element in the project has demolition status, the demolition rule should fire for every sheet.

---

### Wrong or missing note text

**Cause**: Template key mismatch between `rules.json` and `note_templates.json`.

**Debugging**:
1. In `rules.json`, check the `note_section.template_key` value.
2. In `note_templates.json`, verify a matching key exists under `templates`.
3. If the key doesn't match, the `NoteEntry` will have an empty `body`.

---

### `FileNotFoundError` or `json.JSONDecodeError` for config files

**Cause**: Config file missing or malformed.

**Fix**: Ensure `config/rules.json` and `config/note_templates.json` exist and contain valid JSON. Validate with:
```bash
python -m json.tool config/rules.json
python -m json.tool config/note_templates.json
```

---

## Apply errors

### `Cannot write notes — property not available`

**Cause**: The custom property `LayoutAnnotation_SheetNotesText` doesn't exist and couldn't be auto-created.

**Fix** (manual creation in Archicad):
1. Open **Options → Property Manager** (or **File → Property Manager**).
2. Create a new **Property Group**: `LayoutAnnotation`.
3. Create a new **Property**: `SheetNotesText`.
4. Set **Type**: String.
5. Set **Available for**: Layouts.
6. Click OK.
7. Re-run the script.

---

### `Updated 0 layout properties`

**Causes**:
- No matching sheet_id between layouts and generated notes.
- The custom property doesn't exist (see above).
- `ElementId` construction failed for layout GUIDs.

**Debugging**: Check logs for "Could not build ElementId for layout" or "property not available" warnings.

---

### `Exit Code: 127` when running scripts

**Cause**: The Python executable was not found in the terminal's PATH.

**Fix**:
```bash
which python3
# or
python3 scripts/run_annotation.py --port 19723 --apply json
```

Ensure you're using the correct Python environment where `archicad` and `pydantic` are installed.

---

## Output issues

### `SheetNotes.json` is empty or has no sheets

**Cause**: No layouts were found, or all layouts were skipped during note building.

**Debugging**:
1. Check "No phase report for layout X" warnings — indicates a layout GUID mismatch between layouts list and reports dict.
2. Check "No layouts found" warning — run `discover_commands.py` to verify API works.

---

### Notes are identical on every sheet

**This is expected behavior** in the current implementation. Because per-layout element filtering is not yet implemented, ALL elements are attributed to every layout. This means every applicable rule fires on every sheet.

**To fix**: Implement per-layout element filtering by populating the `layout_element_map` parameter in `analyse_all_layouts()`. This requires mapping which elements are visible in each layout's source views.

---

## Logging

All modules use Python's `logging` module. The default level in scripts is `INFO`.

To increase verbosity:
```python
logging.basicConfig(level=logging.DEBUG)
```

Or modify the `logging.basicConfig` call in any script.

Key log messages to watch for:
- `"Connecting to Archicad on port X"` — connection attempt
- `"Connected successfully."` — connection OK
- `"GetAllElements returned N elements."` — extract working
- `"Found N layouts."` — layouts found
- `"Rule 'X' fired for sheet 'Y'."` — (DEBUG) rule evaluation
- `"Exported SheetNotes.json → path"` — successful export
- `"Updated N layouts with notes."` — successful property write

---

## Context-switch recap

1. **Connection fails**: Check Archicad is running, JSON API enabled, correct port, package installed.
2. **Exit code 127**: Python not in PATH. Use `python3` explicitly.
3. **No elements**: Project empty or not fully loaded.
4. **No layouts**: Layout Book is empty. Verify in AC Navigator.
5. **Rules not firing**: Check condition types, template keys, and log at DEBUG level.
6. **Property write fails**: Create `LayoutAnnotation_SheetNotesText` manually in Property Manager.
7. **Identical notes on every sheet**: Expected until per-layout element filtering is implemented.
8. **Config errors**: Validate JSON files with `python -m json.tool`.
9. All logging uses Python `logging` module at INFO level by default.
10. Validate connection with: `curl -X POST http://127.0.0.1:19723 -d '{"command":"IsAlive"}'`.
