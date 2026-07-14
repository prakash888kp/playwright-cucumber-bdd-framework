# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `python scripts/run.py --excel` — run scenarios flagged `Run = YES` in `config/execution-control.xlsx` (primary run mode)
- `python scripts/run.py --tags "@TC_UI_001"` — run a single scenario by its ID tag
- `python scripts/run.py --profile smoke|regression|ui|api|rag` — named suite profiles
- `python scripts/run.py --rerun` — re-run failing scenario IDs from `reports/rerun.txt`
- `python scripts/generate_report.py` — manual rebuild only; every run already auto-creates a timestamped archive `reports/run_<ts>_<env>_<verdict>/` via `scripts/run.py` and appends to `reports/run-history.json`
- `python scripts/generate_excels.py` — regenerate both xlsx workbooks (**overwrites manual edits**)
- `python scripts/dashboard.py` — local web UI at `http://localhost:4444` (pure stdlib): scenario dropdowns, live SSE console, run-history trend chart + report links; spawns `scripts/run.py` so the archive funnel is preserved
- Env knobs: `PARALLEL=n` (xdist workers), `RETRY=n` (rerunfailures), `ENV`, `BROWSER`, `HEADLESS`, `STEP_SCREENSHOTS`, `VISUAL_THRESHOLD` — set in shell before the command
- Lint: `python -m ruff check .` | Setup: `pip install -r requirements.txt` then `python -m playwright install chromium`

## Architecture

pytest-bdd on Playwright (Python, sync API), parallel via pytest-xdist. Three test types coexist, distinguished by tags: `@ui` (browser via POM in `framework/pages/`), `@api` (Playwright request context via `framework/helpers/api_helper.py`), `@rag` (Amazon Bedrock Knowledge Base validation via `framework/helpers/bedrock_helper.py` + `rag_validator.py`, boto3, lazy clients).

UI layering is strict: locators live ONLY in `framework/selectors/<page>_selectors.py` as descriptor dicts (`{"role","name"}`, `{"placeholder"}`, `{"testId"}`, `{"css"}`...), resolved by `BasePage.locate()`. Page objects call BasePage's auto-logged action wrappers (`click`, `fill`, `expect_text`, ...) — they contain flows, not locators or raw Playwright calls. Steps access pages only via `context.pages.<name>` (lazy `PageManager` from the `context` fixture). New page = selectors file + page class + one property in `framework/support/page_manager.py`.

Key flow, spanning multiple files:

- **pytest-bdd wiring** (`tests/`): `test_{ui,api,rag}.py` bind feature dirs via `scenarios()` (`bdd_features_base_dir = features` in `pyproject.toml`); step modules in `tests/steps/` are loaded as `pytest_plugins` from `tests/conftest.py`. All steps use the generic `@step` decorator (NOT `@given/@when/@then`) because the same step text is reused under different keywords across features. Gherkin tags become pytest **markers** — `run.py` turns tag expressions into `-m` expressions by stripping `@`.
- **Config resolution** (`framework/config/env_loader.py`): shell env > `config/env/.env.<ENV>` > root `.env`. Loaded at the top of `tests/conftest.py` and in `scripts/run.py`. Gotcha: python-dotenv keeps an inline `# comment` as the VALUE when the value before it is empty — put comments for empty vars on their own line in `.env` files.
- **Scenario ↔ data linkage**: every scenario carries a unique ID tag (`@TC_UI_001`). The same ID is (a) the `ScenarioID` column in `config/execution-control.xlsx` used by `framework/runners/excel_runner.py` to build a tag expression (with two-way drift audit warnings), and (b) the `TC_ID` key used by `framework/helpers/data_manager.py` to fetch its row from `config/testdata.xlsx`. Adding a scenario requires touching all three (feature file, control sheet, data sheet).
- **Lifecycle** (`tests/conftest.py`): Playwright + browser are session fixtures (one per xdist worker); the `context` fixture (behave-style namespace) creates a browser context/page + PageManager **only for @ui scenarios** (detected via markers). IMPORTANT: pytest-bdd's `scenario.tags` does NOT include feature-level tags — hooks must use `scenario.tags | feature.tags` or node markers.
- **Result collection**: pytest-bdd hooks in conftest time each step, capture errors, and take per-step screenshots (`STEP_SCREENSHOTS=on|failure|off`); each worker writes `reports/results.<worker>.json` + `attachments.<worker>.json` in `pytest_sessionfinish`. Deselected scenarios never appear (unlike behave); runtime skips (RAG without creds, via `pytest.skip` in `pytest_bdd_before_scenario`) appear as skipped.
- **Run funnel**: all run modes route through `scripts/run.py` (spawn pytest with `-m` expression, `-n` for PARALLEL, `--reruns` for RETRY → always `build_report()`); pytest exit code 5 (no tests selected) is mapped to 0. Bypassing with raw `pytest` skips the timestamped archive.
- **Report builder** (`framework/helpers/report_builder.py` + `report_template.html`): merges per-worker results/attachments into one self-contained `html/index.html` — pass-rate donut, stat tiles, search/filter chips, screenshots embedded base64, gallery modal.
- **Visual regression** (`framework/helpers/visual.py`): step `the page should match the visual baseline "<name>"`; baselines in `visual-baselines/<ENV>/` (committed). First run records; later runs pixel-diff (PIL) against `VISUAL_THRESHOLD` % (default 2.0), attaching actual+diff on failure.
- **API schema step**: `the response should match the JSON schema "<file>"` validates via jsonschema against `config/schemas/<file>`.

## Gotchas

- xlsx workbooks are binary — inspect/edit them via `framework/helpers/excel_reader.py` or a small python script, and remember `generate_excels.py` clobbers them.
- Default execution-control flags RAG rows `NO` since they need real AWS access.
- Windows console is cp1252 — avoid non-ASCII characters in `print()` from scripts (the dashboard sets `PYTHONIOENCODING=utf-8` for child runs). PowerShell `Get-Content`/`Set-Content` round-trips also mangle UTF-8 — edit files with proper tooling.
- The JavaScript implementation lives on branch `main`; this Python version is branch `python-migration`.
