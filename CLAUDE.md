# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `npm run test:excel` — run scenarios flagged `Run = YES` in `config/execution-control.xlsx` (primary run mode)
- `npm test -- --tags "@TC_UI_001"` — run a single scenario by its ID tag
- `npm run test:smoke` / `test:regression` / `test:ui` / `test:api` / `test:rag` — cucumber profiles (defined in `cucumber.js`)
- `npm run test:rerun` — re-run failures from `reports/@rerun.txt`
- `npm run report` — manual rebuild only; every run already auto-creates a timestamped archive `reports/run_<ts>_<env>_<verdict>/` via `scripts/run.js` and appends to `reports/run-history.json`
- `npm run generate:excel` — regenerate both xlsx workbooks (**overwrites manual edits**)
- Env overrides: `npx cross-env ENV=dev BROWSER=firefox HEADLESS=false TAGS=@smoke npm test`

## Architecture

Cucumber BDD on Playwright (plain JS, CommonJS). Three test types coexist, distinguished by tags: `@ui` (browser via POM in `src/pages/`), `@api` (Playwright request context via `src/helpers/apiHelper.js`), `@rag` (Amazon Bedrock Knowledge Base validation via `src/helpers/bedrockHelper.js` + `ragValidator.js`).

UI layering is strict: locators live ONLY in `src/selectors/<page>Selectors.js` as descriptor objects (`{role,name}`, `{placeholder}`, `{testId}`, `{css}`...), resolved by `BasePage.locate()`. Page objects call BasePage's auto-logged action wrappers (`click`, `fill`, `expectText`, ...) — they contain flows, not locators or raw Playwright calls. Steps access pages only via `this.pages.<name>` (lazy `PageManager` created per UI scenario in hooks). New page = selectors file + page class + one getter in `src/support/pageManager.js`.

Key flow, spanning multiple files:

- **Config resolution** (`src/config/envLoader.js`, loaded at the top of `cucumber.js`): shell/CLI env > `config/env/.env.<ENV>` > root `.env`. `cucumber.js` turns `TAGS`/`PARALLEL`/`RETRY` env vars into cucumber options — env vars are how run behavior is controlled, not CLI flags alone.
- **Scenario ↔ data linkage**: every scenario carries a unique ID tag (`@TC_UI_001`). The same ID is (a) the `ScenarioID` column in `config/execution-control.xlsx` used by `src/runners/excelRunner.js` to build a tag expression, and (b) the `TC_ID` key used by `src/helpers/dataManager.js` to fetch its row from `config/testdata.xlsx`. Adding a scenario requires touching all three (feature file, control sheet, data sheet).
- **Lifecycle** (`src/support/hooks.js` + `world.js`): one browser per worker (`BeforeAll`); a fresh context/page is created per scenario **only when tagged `@ui`** — API/RAG scenarios run without a browser context. Tracing and failure screenshots are handled here. `src/support` must load before `src/steps` (require order in `cucumber.js`) so `this.log` exists in tagged hooks.
- **Run funnel**: all npm test scripts route through `scripts/run.js` (spawn cucumber → always `buildReport()` from `src/helpers/reportBuilder.js`); `excelRunner.js` reuses `runAndReport`. Bypassing with raw `npx cucumber-js` skips the timestamped archive.
- **Per-step screenshots**: `AfterStep` in `hooks.js` attaches a screenshot for every UI step (`STEP_SCREENSHOTS=on|failure|off`).
- **RAG skip behavior**: a tagged `Before({tags: '@rag'})` in `src/steps/rag/ragSteps.js` returns `'skipped'` when AWS creds or `BEDROCK_KB_ID` are missing — RAG scenarios skip rather than fail on unconfigured machines.

## Gotchas

- `multiple-cucumber-html-reporter` v4 is ESM-only; `scripts/generateReport.js` uses `await import()` with the **named** `generate` export.
- xlsx workbooks are binary — inspect/edit them via `src/helpers/excelReader.js` or a small node script, and remember `generate:excel` clobbers them.
- Default execution-control flags RAG rows `NO` since they need real AWS access.
