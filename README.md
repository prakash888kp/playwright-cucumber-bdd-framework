# Playwright + Cucumber BDD Framework (UI · API · RAG)

Enterprise test automation framework in JavaScript combining:

- **UI testing** — Playwright with Page Object Model
- **API testing** — Playwright `APIRequestContext` wrapper
- **RAG validation** — Amazon Bedrock Knowledge Base (`RetrieveAndGenerate`) with keyword-coverage, citation, and LLM-as-judge checks
- **BDD** — Cucumber feature files with tag-based selection
- **Excel-driven execution** — flip scenarios on/off and manage test data in xlsx
- **Winston logging**, per-scenario traces/screenshots, and a rich HTML dashboard

## Quick start

```bash
npm install                 # also installs Chromium via postinstall
npm run generate:excel      # (re)create the two workbooks with defaults
npm run test:excel          # run everything flagged YES in the control sheet
npm run report              # build reports/html/index.html

```

## Three ways to run

| Mode | How | Use case |
|------|-----|----------|
| 1. Excel-driven | `npm run test:excel` | Manual testers pick scenarios by setting `Run = YES` in `config/execution-control.xlsx` |
| 2. Env-driven | Set `TAGS`, `BROWSER`, `ENV`, etc. in `.env` / `config/env/.env.<env>`, then `npm run test:env` | CI pipelines with per-environment config |
| 3. Command line | `npm test -- --tags "@smoke"` or profiles: `npm run test:smoke`, `test:regression`, `test:ui`, `test:api`, `test:rag` | Ad-hoc local runs |
| 4. Web dashboard | `npm run dashboard` → http://localhost:4444 | Pick scenarios from dropdowns, trigger any mode, watch live console output, browse past run reports |

### The dashboard (`npm run dashboard`)

A zero-dependency local web UI (`scripts/dashboard.js`) with two tabs:

- **Execution** — choose the trigger (selected scenarios / Excel control sheet / profile), pick env, browser, headless, and screenshot mode from dropdowns, then run with a live streaming console. Scenario checkboxes are loaded from `execution-control.xlsx` (rows with `Run = YES` come pre-selected).
- **Run History** — stats (total runs, pass rate, latest verdict) plus a table of every archived run from `run-history.json`, each with a one-click link that opens its timestamped HTML report.

Runs triggered from the dashboard go through the same funnel as every other mode, so archives and history keep working identically. Port: `DASHBOARD_PORT` (default 4444).

Modifier examples:

```bash
npm run test:headed                       # visible browser
npx cross-env BROWSER=firefox npm test    # different browser
npx cross-env ENV=dev npm test            # different environment (config/env/.env.dev)
npm run test:rerun                        # re-run only failures from last run
```

Priority when settings conflict: **CLI / shell env > config/env/.env.<ENV> > .env defaults**.

## The two workbooks (`config/`)

**execution-control.xlsx** — sheet `ExecutionControl`: one row per scenario (`Feature`, `ScenarioID`, `ScenarioName`, `Type`, `Run`). The runner builds a cucumber tag expression from every row where `Run = YES`. The `ScenarioID` must match a tag on the scenario (e.g. `@TC_UI_001`).

**testdata.xlsx** — one sheet per module (`LoginData`, `CartData`, `APIData`, `RAGData`), rows keyed by `TC_ID`. Steps fetch rows via `dataManager.getData(sheet, tcId)`.

> `npm run generate:excel` **overwrites** both files with defaults — edit the xlsx directly for day-to-day changes.

## RAG validation (Amazon Bedrock)

Set in your shell or `.env`:

```
AWS_REGION=us-east-1
BEDROCK_KB_ID=<your knowledge base id>
# plus AWS credentials via env vars, profile, or SSO
```

RAG scenarios validate three ways (see `src/helpers/ragValidator.js`):

1. **Keyword coverage** — answer must contain ≥ `RAG_MIN_KEYWORD_COVERAGE` of the expected keywords from `RAGData`
2. **Citations** — `RetrieveAndGenerate` must return grounded references
3. **LLM-as-judge** — a Claude model on Bedrock scores faithfulness/relevance 0–10; must be ≥ `RAG_MIN_JUDGE_SCORE` and verdict `PASS`

Without AWS credentials or `BEDROCK_KB_ID`, RAG scenarios **skip** instead of failing.

## Reports & diagnostics

**Every run automatically produces a timestamped archive** (pass or fail) so history is never overwritten:

```
reports/
  run_2026-07-14_12-59-46_qa_PASSED/
    html/index.html          # rich dashboard — per-feature drill-down
    cucumber-report.json     # raw results for this run
    cucumber-report.html     # cucumber's single-file report
    traces/                  # Playwright traces from this run (on failure)
  run-history.json           # ledger of all runs (env, tags, pass/fail counts)
  latest-run.txt             # path to the newest archive
```

- **Per-step screenshots**: every UI step embeds a screenshot in the report (`STEP_SCREENSHOTS=on|failure|off` in `.env`) — visual evidence for each action and validation
- `npm run report` — manual rebuild from the last `cucumber-report.json` (rarely needed; runs auto-report)
- `npx playwright show-trace <run folder>/traces/<file>.zip` — step-through debugging
- `logs/execution-<date>.log` — winston log with scenario-scoped labels
- `npm run test:rerun` — re-run only last run's failures (`reports/@rerun.txt`)

## Structure

```
config/
  env/.env.{dev,qa,prod}     # per-environment settings
  execution-control.xlsx     # run/skip toggles
  testdata.xlsx              # test data by TC_ID
src/
  config/envLoader.js        # layered env resolution
  features/{ui,api,rag}/     # .feature files
  steps/{ui,api,rag}/        # step definitions (pure orchestration, no locators)
  selectors/                 # one selector file per page — the only place locators live
  pages/                     # page objects: declarative flows on BasePage actions
  support/world.js, hooks.js # per-scenario browser/API/Bedrock lifecycle
  support/pageManager.js     # lazy page-object factory (this.pages.loginPage)
  helpers/                   # logger, excelReader, dataManager, apiHelper,
                             # bedrockHelper, ragValidator, commonUtils
  runners/excelRunner.js     # run mode 1
scripts/
  generateExcels.js          # scaffold the workbooks
  generateReport.js          # HTML dashboard
```

## Adding a new scenario

1. Write the scenario in a `.feature` file and tag it with a unique ID (`@TC_UI_004`) plus suite tags (`@ui @regression`)
2. Add step definitions (reuse existing generic steps where possible)
3. Add a test-data row with that `TC_ID` in the right sheet of `testdata.xlsx`
4. Add a row in `execution-control.xlsx` with `Run = YES`
