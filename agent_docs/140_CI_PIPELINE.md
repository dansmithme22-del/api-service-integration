# CI Pipeline

How the GitHub Actions pipeline works — what runs, when, and what the
green/red status mean.

Authoritative file: `.github/workflows/ci.yml`. Config files involved:
`pyproject.toml` (ruff + pytest), `.github/dependabot.yml` (dep updates).

---

## Context-switch recap (10 bullets)

1. CI runs on every push to `main` and every pull request, plus manual
   trigger from the Actions tab.
2. Three jobs run in **parallel** so a typical run finishes in under
   3 minutes: `lint`, `test`, `validate-configs`.
3. A fourth `ci-summary` job rolls them up — that's the one that
   sets the badge state.
4. **Lint is advisory** right now (`continue-on-error: true`).
   Findings show up in the GitHub Annotations panel but don't fail
   the build. Tightens over time.
5. **Tests are blocking** — if any test fails the build is red.
   Pipeline tests are designed to run offline; nothing in CI hits
   live APIs or Archicad.
6. **JSON validation is blocking** — every file under `config/` and
   `assets/` must parse. Catches typos in the canonical CSI / AIA /
   IBC / drafting data before they break the runtime.
7. Slim install: CI only installs the dependencies the offline test
   suite actually imports (~7 packages, ~30 seconds). The heavy AI
   stack (anthropic, openai, google-genai, chromadb,
   sentence-transformers) is not installed in CI.
8. Concurrency control: pushing a new commit to the same branch /
   PR cancels the in-flight run. No wasted CI minutes.
9. **Dependabot** opens weekly PRs for Python dep updates and
   monthly PRs for GitHub Actions updates. Groups AI provider SDKs,
   testing tools, and the ML stack together so reviews are coherent.
10. Pipeline targets Python 3.11 (matching the local `.venv`).

---

## The jobs

### `lint` — ruff

Runs `ruff check . --output-format=github` so findings appear inline on
PRs. Currently advisory: started lenient (F + E9 + B rules only) so the
existing codebase doesn't go red on day one. Tighten the rule set in
`pyproject.toml` once the codebase is clean for the current set.

### `test` — pytest

Runs the full offline test suite from `tests/`:

```bash
pytest tests/ -v --tb=short --color=yes
```

Plus a pre-flight that imports every core module to catch syntax /
import errors before pytest's collection phase muddies the trace.

If a test requires live API access or a running Archicad instance,
mark it:

```python
@pytest.mark.online       # requires GEMINI / ANTHROPIC / OPENAI key
@pytest.mark.archicad     # requires Archicad on port 19723
@pytest.mark.slow         # > a few seconds
def test_something_heavy():
    ...
```

Markers are registered in `pyproject.toml`. CI does NOT pass `-m online`
or `-m archicad` so those tests are skipped by default. Local runs can
opt in via `pytest -m "not online"` etc.

### `validate-configs` — JSON parse check

Walks `config/**/*.json` and `assets/**/*.json`. Every file must parse.
If any throws, the job lists the errors and fails.

This is cheap insurance — a typo in `config/csi_master_format.json`
breaks the runtime silently otherwise.

### `ci-summary` — gate

Always runs (`if: always()`), checks the results of `lint`, `test`,
`validate-configs`. Fails the workflow if `test` or `validate-configs`
fail. Lint result is informational only.

---

## What CI does NOT do

Deliberately excluded from CI to keep it fast, reliable, and free:

- **No API calls.** Anthropic / Gemini / OpenAI tests are marked
  `@pytest.mark.online` and excluded. Local devs can run them with
  their own keys.
- **No Archicad.** No headless Archicad in CI. Tests that touch the
  JSON API are marked `@pytest.mark.archicad` and excluded.
- **No model downloads.** The `sentence-transformers` model is not
  pulled in CI. Knowledge-DB tests are either skipped or stubbed.
- **No PDF rendering tests.** Don't render the 50 MB reference PDF
  on every push.
- **No coverage reporting yet.** Add `pytest-cov` + Codecov when
  there's a target coverage number worth defending.
- **No deployment.** This isn't a service. CI is "continuous
  integration" — verify the code still works. No "continuous
  delivery" target.

---

## Adding a new check

1. Either add a new job in `.github/workflows/ci.yml`, or extend an
   existing one.
2. Wire it into `ci-summary.needs` if it should block.
3. Keep job timeout < 10 minutes — a slow CI is a CI nobody waits for.
4. Run it locally first with `act` (https://github.com/nektos/act) or
   manually before pushing to verify the YAML is valid.

---

## Dependabot

`.github/dependabot.yml` schedules:

- **Weekly** Python dep PRs (Mondays 9 AM ET), max 5 open at a time
- **Monthly** GitHub Actions version PRs

Grouped sets:

- `ai-providers` — `anthropic`, `openai`, `google-genai`
- `dev-tools` — `pytest*`, `ruff`
- `ml-stack` — `chromadb`, `sentence-transformers`, `torch*`,
  `transformers`

Grouping means a Tuesday PR can be one PR with three SDK bumps instead
of three separate ones. Easier to review, easier to revert.

---

## Reading the badge

The badge in `README.md` links to the latest CI run on `main`. Three
states:

- ✅ **Green (passing)** — last main-branch run succeeded.
- ❌ **Red (failing)** — last main-branch run failed. Click the badge
  to jump straight to the run log.
- 🟡 **Yellow (in-progress / no runs yet)** — CI is currently running
  or has never run for this branch.

PRs get the same per-commit status indicators in the Checks tab.

---

## Local pre-flight before pushing

To run what CI runs without pushing first:

```bash
# Same install as the CI test job
pip install pydantic pdfplumber pypdfium2 Pillow shapely numpy \
            python-dotenv pytest ruff

# Same lint as CI
ruff check . --output-format=github

# Same tests as CI
pytest tests/ -v --tb=short

# Same JSON validation as CI
python -c "
import json
from pathlib import Path
errs = []
for root in ('config', 'assets'):
    for p in Path(root).rglob('*.json'):
        try: json.loads(p.read_text())
        except Exception as e: errs.append(f'{p}: {e}')
print(f'{len(errs)} errors' if errs else 'all valid')
"
```

If those three pass locally, the CI will pass too.

---

## Cost

GitHub Actions free tier on a public repo is unlimited; on a private
repo you get 2,000 minutes/month. A typical run uses ~3-5 minutes (all
three jobs in parallel). At ~50 runs/month that's ~150-250 minutes —
well inside the free allotment.

If the cost ever matters, the levers are:

1. Skip the dep install on doc-only PRs (paths-ignore for `**/*.md`).
2. Cache the pip dependencies more aggressively
   (`actions/cache@v4`).
3. Use a self-hosted runner (your own machine) for free unlimited.
