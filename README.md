# Playwright + Behave BDD Framework (UI · API · RAG) — Python

Enterprise test automation framework in Python combining:

- **UI testing** — Playwright with Page Object Model
- **API testing** — Playwright `APIRequestContext` wrapper
- **RAG validation** — Amazon Bedrock Knowledge Base (`RetrieveAndGenerate`) with keyword-coverage, citation, and LLM-as-judge checks (boto3)
- **BDD** — behave (Cucumber for Python) feature files with tag-based selection
- **Excel-driven execution** — flip scenarios on/off and manage test data in xlsx
- **Logging**, per-scenario traces/screenshots, and a rich self-contained HTML dashboard (pure Python, no Node.js)

## Quick start

```bash
pip install -r requirements.txt
python -m playwright install chromium
python scripts/generate_excels.py      # (re)create the two workbooks with defaults
python scripts/run.py --excel          # run everything flagged YES in the control sheet
```

## Four ways to run

| Mode | How | Use case |
|------|-----|----------|
| 1. Excel-driven | `python scripts/run.py --excel` | Manual testers pick scenarios by setting `Run = YES` in `config/execution-control.xlsx` |
| 2. Env-driven | Set `TAGS`, `BROWSER`, `ENV`, etc. in `.env` / `config/env/.env.<env>`, then `python scripts/run.py` | CI pipelines with per-environment config |
| 3. Command line | `python scripts/run.py --tags "@smoke"` or profiles: `--profile smoke\|regression\|ui\|api\|rag` | Ad-hoc local runs |
| 4. Web dashboard | `python scripts/dashboard.py` → http://localhost:4444 | Pick scenarios from dropdowns, trigger any mode, watch live console output, browse past run reports |

Modifier examples (set env vars before the command):

```powershell
$env:HEADLESS='false'; python scripts/run.py --tags "@ui"    # visible browser
$env:BROWSER='firefox'; python scripts/run.py                # different browser
$env:ENV='dev'; python scripts/run.py                        # different environment
python scripts/run.py --rerun                                # re-run only failures from last run
```

Priority when settings conflict: **shell env > config/env/.env.<ENV> > .env defaults**.

### The dashboard (`python scripts/dashboard.py`)

A pure-stdlib local web UI with two tabs:

- **Execution** — choose the trigger (selected scenarios / Excel control sheet / profile), pick env, browser, headless, and screenshot mode from dropdowns, then run with a live streaming console. Scenario checkboxes are loaded from `execution-control.xlsx` (rows with `Run = YES` come pre-selected).
- **Run History** — stats plus a table of every archived run from `run-history.json`, each with a one-click link to its timestamped HTML report.

Runs triggered from the dashboard go through the same funnel as every other mode. Port: `DASHBOARD_PORT` (default 4444).

## The two workbooks (`config/`)

**execution-control.xlsx** — sheet `ExecutionControl`: one row per scenario (`Feature`, `ScenarioID`, `ScenarioName`, `Type`, `Run`). The runner builds a behave tag expression from every row where `Run = YES`. The `ScenarioID` must match a tag on the scenario (e.g. `@TC_UI_001`).

**testdata.xlsx** — one sheet per module (`LoginData`, `CartData`, `APIData`, `RAGData`), rows keyed by `TC_ID`. Steps fetch rows via `data_manager.get_data(sheet, tc_id)`.

> `python scripts/generate_excels.py` **overwrites** both files with defaults — edit the xlsx directly for day-to-day changes.

## RAG validation (Amazon Bedrock)

Set in your shell or `.env`:

```
AWS_REGION=us-east-1
BEDROCK_KB_ID=<your knowledge base id>
# plus AWS credentials via env vars, profile, or SSO
```

RAG scenarios validate three ways (see `framework/helpers/rag_validator.py`):

1. **Keyword coverage** — answer must contain ≥ `RAG_MIN_KEYWORD_COVERAGE` of the expected keywords from `RAGData`
2. **Citations** — `RetrieveAndGenerate` must return grounded references
3. **LLM-as-judge** — a Claude model on Bedrock scores faithfulness/relevance 0–10; must be ≥ `RAG_MIN_JUDGE_SCORE` and verdict `PASS`

Without AWS credentials or `BEDROCK_KB_ID`, RAG scenarios **skip** instead of failing.

## Reports & diagnostics

**Every run automatically produces a timestamped archive** (pass or fail) so history is never overwritten:

```
reports/
  run_2026-07-14_21-57-21_qa_PASSED/
    html/index.html          # rich self-contained dashboard (screenshots embedded)
    behave-report.json       # raw results for this run
    traces/                  # Playwright traces from this run (on failure)
  run-history.json           # ledger of all runs (env, tags, pass/fail counts)
  latest-run.txt             # path to the newest archive
```

- **Per-step screenshots**: every UI step embeds a screenshot in the report (`STEP_SCREENSHOTS=on|failure|off` in `.env`) — visual evidence for each action and validation
- `python scripts/generate_report.py` — manual rebuild from the last `behave-report.json` (rarely needed; runs auto-report)
- `python -m playwright show-trace <run folder>/traces/<file>.zip` — step-through debugging
- `logs/execution-<date>.log` — execution log with scenario-scoped labels
- `python scripts/run.py --rerun` — re-run only last run's failures (`reports/rerun.txt`)

## Structure

```
config/
  env/.env.{dev,qa,prod}       # per-environment settings
  execution-control.xlsx       # run/skip toggles
  testdata.xlsx                # test data by TC_ID
features/
  {ui,api,rag}/*.feature       # Gherkin feature files
  steps/                       # step definitions (pure orchestration, no locators)
  environment.py               # behave hooks: browser/API/Bedrock lifecycle, screenshots
framework/
  config/env_loader.py         # layered env resolution
  selectors/                   # one selector file per page — the only place locators live
  pages/                       # page objects: declarative flows on BasePage actions
  support/page_manager.py      # lazy page-object factory (context.pages.login_page)
  helpers/                     # logger, excel_reader, data_manager, api_helper,
                               # bedrock_helper, rag_validator, report_builder, common_utils
  runners/excel_runner.py      # run mode 1
scripts/
  run.py                       # universal run funnel (all modes; always archives a report)
  dashboard.py                 # run mode 4 — local web UI
  generate_excels.py           # scaffold the workbooks
  generate_report.py           # manual HTML dashboard rebuild
```

## Adding a new scenario

1. Write the scenario in a `.feature` file and tag it with a unique ID (`@TC_UI_004`) plus suite tags (`@ui @regression`)
2. Add step definitions (reuse existing generic steps where possible)
3. Add a test-data row with that `TC_ID` in the right sheet of `testdata.xlsx`
4. Add a row in `execution-control.xlsx` with `Run = YES`

## Notes vs the JavaScript version (branch `main`)

- Same feature files, same workbooks, same run modes, same dashboard UI, same report archive/history behavior
- Report dashboard is generated by pure Python (`framework/helpers/report_builder.py` + `report_template.html`) — no Node.js anywhere
- behave runs scenarios sequentially; the `PARALLEL` setting from the JS version does not apply
