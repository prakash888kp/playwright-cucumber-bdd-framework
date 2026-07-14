# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `python scripts/run.py --excel` — run scenarios flagged `Run = YES` in `config/execution-control.xlsx` (primary run mode)
- `python scripts/run.py --tags "@TC_UI_001"` — run a single scenario by its ID tag
- `python scripts/run.py --profile smoke|regression|ui|api|rag` — named suite profiles
- `python scripts/run.py --rerun` — re-run failing scenario IDs from `reports/rerun.txt`
- `python scripts/generate_report.py` — manual rebuild only; every run already auto-creates a timestamped archive `reports/run_<ts>_<env>_<verdict>/` via `scripts/run.py` and appends to `reports/run-history.json`
- `python scripts/generate_excels.py` — regenerate both xlsx workbooks (**overwrites manual edits**)
- `python scripts/dashboard.py` — local web UI at `http://localhost:4444` (pure stdlib): scenario dropdowns, live SSE console, run history with report links; spawns `scripts/run.py` so the archive funnel is preserved
- Env overrides: set shell vars before running, e.g. `$env:ENV='dev'; $env:BROWSER='firefox'; $env:HEADLESS='false'; python scripts/run.py --tags "@smoke"`
- Setup: `pip install -r requirements.txt` then `python -m playwright install chromium`

## Architecture

behave BDD on Playwright (Python, sync API). Three test types coexist, distinguished by tags: `@ui` (browser via POM in `framework/pages/`), `@api` (Playwright request context via `framework/helpers/api_helper.py`), `@rag` (Amazon Bedrock Knowledge Base validation via `framework/helpers/bedrock_helper.py` + `rag_validator.py`, boto3, lazy clients).

UI layering is strict: locators live ONLY in `framework/selectors/<page>_selectors.py` as descriptor dicts (`{"role","name"}`, `{"placeholder"}`, `{"testId"}`, `{"css"}`...), resolved by `BasePage.locate()`. Page objects call BasePage's auto-logged action wrappers (`click`, `fill`, `expect_text`, ...) — they contain flows, not locators or raw Playwright calls. Steps access pages only via `context.pages.<name>` (lazy `PageManager` created per UI scenario in `features/environment.py`). New page = selectors file + page class + one property in `framework/support/page_manager.py`.

Key flow, spanning multiple files:

- **Config resolution** (`framework/config/env_loader.py`): shell env > `config/env/.env.<ENV>` > root `.env`. Loaded at the top of `features/environment.py` and in `scripts/run.py`. Gotcha: python-dotenv keeps an inline `# comment` as the VALUE when the value before it is empty — put comments for empty vars on their own line in `.env` files.
- **Scenario ↔ data linkage**: every scenario carries a unique ID tag (`@TC_UI_001`). The same ID is (a) the `ScenarioID` column in `config/execution-control.xlsx` used by `framework/runners/excel_runner.py` to build a tag expression, and (b) the `TC_ID` key used by `framework/helpers/data_manager.py` to fetch its row from `config/testdata.xlsx`. Adding a scenario requires touching all three (feature file, control sheet, data sheet).
- **Step matching**: all step definitions use behave's `@step` decorator (NOT `@given/@when/@then`) because behave matches by keyword and the same step text is reused under different keywords across features (e.g. "I login with the loaded credentials" is a When in login.feature and a Given-chained And in cart.feature).
- **Lifecycle** (`features/environment.py`): one browser per run (`before_all`); a fresh context/page is created per scenario **only when tagged `@ui`** — API/RAG scenarios run without a browser context. Tracing, per-step screenshots (`STEP_SCREENSHOTS=on|failure|off`), and failure screenshots are handled here; screenshots + text attachments are recorded in `reports/attachments.json` for the report builder.
- **Run funnel**: all run modes route through `scripts/run.py` (spawn `python -m behave` with json output → always `build_report()` from `framework/helpers/report_builder.py`). Bypassing with raw `behave` skips the timestamped archive.
- **Report builder** (`framework/helpers/report_builder.py` + `report_template.html`): pure Python replacement for the old Node reporter — renders a self-contained `html/index.html` (screenshots embedded base64). behave's JSON marks tag-EXCLUDED scenarios as "skipped"; the builder drops them by checking for an attachments-manifest key (hooks only run for selected scenarios), so runtime skips (RAG without creds) still show as skipped.
- **RAG skip behavior**: `before_scenario` in `environment.py` calls `scenario.skip()` when AWS creds or `BEDROCK_KB_ID` are missing — RAG scenarios skip rather than fail on unconfigured machines.

## Gotchas

- xlsx workbooks are binary — inspect/edit them via `framework/helpers/excel_reader.py` or a small python script, and remember `generate_excels.py` clobbers them.
- Default execution-control flags RAG rows `NO` since they need real AWS access.
- behave is single-process; there is no parallel execution (the JS version's `PARALLEL` env var has no effect here).
- Windows console is cp1252 — avoid non-ASCII characters in `print()` from scripts (the dashboard sets `PYTHONIOENCODING=utf-8` for child runs).
- The JavaScript implementation lives on branch `main`; this Python version is branch `python-migration`.
