# 30 — ARCHICAD INTEGRATION

## Purpose

Concrete, reproducible guide for connecting to and operating against a **live Archicad instance**. Covers prerequisites, connection mechanics, execution modes, add-on requirements, and a minimal smoke test.

## When to read this

- Before running any script against a live Archicad instance.
- When troubleshooting connection issues.
- When setting up a new development or production environment.

---

## 1. Preconditions

### Archicad version compatibility

| Version | Status | Notes |
|---|---|---|
| **Archicad 29** | **Primary target** | Default port 19723. Fully tested. |
| Archicad 28 | Should work | SDK API differences possible; `execute_raw()` has a fallback path. |
| Archicad 27 | Partial | `GetPropertyIds` available from AC 27+. Older versions lack it. |
| Archicad 26 and earlier | Not supported | Missing required JSON commands. |

### Enabling the JSON/Python API

1. Open Archicad 29.
2. Navigate to:
   - **macOS**: `Archicad → Settings → Work Environment`
   - **Windows**: `Options → Work Environment → Experimental` (or `Edit → Preferences`)
3. Find the **Experimental** section.
4. Enable **Python / JSON API**.
5. Set the **port** to `19723` (default) or your preferred port.
6. Restart Archicad if prompted.

### Installing the Python package

```bash
pip install archicad
```

The `archicad` PyPI package (maintained by Graphisoft) provides the `ACConnection` class, typed command wrappers, and type definitions. This repo requires version ≥27.0.0:

```bash
pip install "archicad>=27.0.0"
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

---

## 2. Connection details

### How the code connects

```python
# src/connection.py
from archicad import ACConnection

conn = ACConnection.connect(19723)
commands = conn.commands     # typed command methods
types = conn.types           # type constructors
utilities = conn.utilities   # helper utilities
```

This repo wraps the SDK in `ArchicadConnection` (see `src/connection.py`) so the rest of the codebase never imports `archicad` directly.

### Where port/host are configured

| Setting | Location | Default |
|---|---|---|
| Port | `src/connection.py::DEFAULT_PORT` | `19723` |
| Port | CLI `--port` argument on all scripts | `19723` |
| Host | Hardcoded to `127.0.0.1` (localhost) | Not configurable (AC only listens locally) |

**The Archicad JSON API only accepts connections from localhost.** Remote connections are not supported by the API.

### How to validate the connection

**Method 1: Use the discovery script**
```bash
python scripts/discover_commands.py --port 19723
```
If successful, it prints the number of available commands and types. If it fails, it prints a clear error with instructions.

**Method 2: Python REPL**
```python
from archicad import ACConnection
conn = ACConnection.connect(19723)
info = conn.commands.GetProductInfo()
print(info)  # Should print Archicad version info
```

**Method 3: Raw HTTP**
```bash
curl -X POST http://127.0.0.1:19723 \
  -H "Content-Type: application/json" \
  -d '{"command": "IsAlive"}'
```
Expected response: `{"succeeded": true, "result": {"isAlive": true}}`

---

## 3. Execution modes

### Mode A: Run from external terminal (recommended)

The standard way to use this tool. Python runs outside Archicad and communicates via the JSON API.

```bash
# Full pipeline — export JSON only (safe, no AC mutation)
python scripts/run_annotation.py --port 19723 --apply json

# Full pipeline — write to Archicad properties (mutating)
python scripts/run_annotation.py --port 19723 --apply property

# Both
python scripts/run_annotation.py --port 19723 --apply both

# Preview without writing anything
python scripts/run_annotation.py --port 19723 --dry-run
```

**Requirements**: Python 3.10+, `archicad` and `pydantic` packages installed, Archicad running with JSON API enabled.

### Mode B: Run from Archicad's Python Palette

Archicad 27+ includes a built-in Python Palette (a code editor inside AC). You can paste or load scripts there.

1. Open the Python Palette: **Window → Palettes → Python Palette**
2. Either:
   - **Paste** the content of `scripts/quick_demo.py` (or any script) into the palette.
   - **Load** a `.py` file from disk.
3. The `archicad` module is pre-installed in the palette's Python environment.
4. **Caveat**: The palette uses its own Python interpreter. You may need to install `pydantic` into it:
   ```python
   import subprocess
   subprocess.check_call(["pip", "install", "pydantic"])
   ```
5. The `sys.path.insert(0, ...)` line in each script ensures the `src/` package is importable regardless of working directory.

### Mode C: C++ Add-On (for direct text placement)

If you need the C++ Add-On for direct text placement:

1. Build the Add-On using the Archicad 29 API DevKit and CMake.
2. Install it: copy the `.apx` file to Archicad's Add-Ons folder.
3. The Add-On registers a command `LayoutAnnotator::PlaceText`.
4. Python can invoke it via:
   ```python
   conn.execute_raw("ExecuteAddOnCommand", {
       "addOnCommandId": {
           "commandNamespace": "LayoutAnnotator",
           "commandName": "PlaceText",
       },
       "addOnCommandParameters": {
           "layoutGuid": "<guid>",
           "text": "Note text...",
           "x": 10.0, "y": 10.0,
           "fontSize": 2.5,
       },
   })
   ```

See `addons/layout_annotator_cpp/README.md` for the skeleton implementation.

---

## 4. Required add-ons

### Built-in JSON API (required)

The standard Archicad JSON API must be enabled (see section 1). No additional add-on is needed for the core pipeline.

### Additional JSON Commands Add-On / Tapir (optional)

The [Tapir (Additional JSON Commands) Add-On](https://github.com/nickeltin/archicad-additional-json-commands) extends the JSON API with extra commands. This repo does **not** depend on it, but:

- `text_placer.py` would benefit from a `CreateTextElement` command if Tapir adds one.
- Run `scripts/discover_commands.py` after installing Tapir to see what new commands are available.

### Layout Annotator C++ Add-On (optional)

Located in `addons/layout_annotator_cpp/`. This is a skeleton — it must be built from source. Only needed if you want direct 2D text placement on layouts (Approach B from the architecture doc).

---

## 5. Minimal smoke test

### Prerequisites
- Archicad 29 running with a project open (any project with at least one layout).
- JSON API enabled on port 19723.
- Python dependencies installed (`pip install -r requirements.txt`).

### Step 1: Validate connection
```bash
python scripts/discover_commands.py --port 19723
```
**Expected**: A list of available commands (typically 50–100+) and types.  
**If it fails**: Check that Archicad is running, JSON API is enabled, and the port matches.

### Step 2: Run the quick demo
```bash
python scripts/quick_demo.py --port 19723
```
**Expected**:
- "Available Commands (showing first 20 of N)" — should show real command names.
- "Retrieved X raw elements" — X should be > 0 if the project has elements.
- "Found Y layouts" — Y should be > 0 if layouts exist.
- "Full output written to .../output/SheetNotes.json" — file should exist.

### Step 3: Run full pipeline (dry-run)
```bash
python scripts/run_annotation.py --port 19723 --dry-run
```
**Expected**: JSON output to stdout showing `ProjectNotesOutput` with sheets and notes.

### Step 4: Run full pipeline (export)
```bash
python scripts/run_annotation.py --port 19723 --apply json
```
**Expected**: Files created in `output/`:
- `SheetNotes.json`
- `per_sheet/A-101.json` (etc.)
- `flat_text/A-101.txt` (etc.)

### Step 5: (Optional) Write to Archicad properties
```bash
python scripts/run_annotation.py --port 19723 --apply property
```
**To confirm it worked**: In Archicad, select a Layout in the Layout Book, open the Properties panel, and check for:
- **Group**: `LayoutAnnotation`
- **Property**: `SheetNotesText`
- **Value**: Should contain the generated note text.

If the property doesn't exist, you'll see a log instruction to create it manually in Property Manager.

### Offline smoke test (no Archicad needed)
```bash
python scripts/quick_demo.py --mock
```
**Expected**: Full pipeline runs with synthetic data, outputs `SheetNotes.json`.

---

## 6. Archicad JSON commands used by this codebase

| Command | Used in | Purpose |
|---|---|---|
| `GetAllElements` | `src/extract/elements.py` | List all element GUIDs in the model |
| `GetElementsByType` | `src/extract/elements.py` | Fallback: get elements of a specific type |
| `GetPropertyIds` | `src/extract/properties.py` | Resolve property name → internal ID |
| `GetPropertyValuesOfElements` | `src/extract/properties.py` | Read property values for a batch of elements |
| `GetAllPropertyNames` | `src/extract/properties.py` | Enumerate all property definitions |
| `SetPropertyValuesOfElements` | `src/extract/properties.py`, `src/apply/property_writer.py` | Write property values |
| `GetNavigatorItemTree` | `src/extract/layouts.py` | Retrieve the Layout Book navigator tree |
| `GetElementsByType("Drawing")` | `src/extract/layouts.py` | Get drawings placed on layouts |
| `CreatePropertyDefinition` | `src/apply/property_writer.py` | Attempt to create the custom property (may not be available) |
| `ExecuteAddOnCommand` | `src/apply/text_placer.py` | Invoke the C++ Add-On for text placement |

---

## Context-switch recap

1. Archicad 29 is the primary target. JSON API must be enabled on port 19723.
2. Install: `pip install archicad pydantic` (or `pip install -r requirements.txt`).
3. Connection is localhost-only (`127.0.0.1:<port>`).
4. Validate with: `python scripts/discover_commands.py`.
5. The `archicad` PyPI package provides `ACConnection`, `commands`, `types`.
6. Two execution modes: external terminal (recommended) or Archicad's Python Palette.
7. C++ Add-On is optional and only for direct text placement.
8. `--apply json` never mutates Archicad. `--apply property` writes to custom properties.
9. The `LayoutAnnotation_SheetNotesText` property may need manual creation in AC's Property Manager.
10. Smoke test: `discover_commands.py` → `quick_demo.py` → `run_annotation.py --dry-run` → `run_annotation.py --apply json`.
