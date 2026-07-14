/**
 * Global hooks — browser per worker, fresh context+page per scenario,
 * tracing/video per env flags, screenshot + trace attached on failure.
 */
const { BeforeAll, AfterAll, Before, After, AfterStep, Status } = require('@cucumber/cucumber');
const { chromium, firefox, webkit } = require('playwright');
const path = require('path');
const fs = require('fs');
const { logger, scenarioLogger } = require('../helpers/logger');

let browser;
const TRACE_DIR = path.resolve(__dirname, '..', '..', 'reports', 'traces');
const VIDEO_DIR = path.resolve(__dirname, '..', '..', 'reports', 'videos');

const browsers = { chromium, firefox, webkit };

BeforeAll(async function () {
  const name = (process.env.BROWSER || 'chromium').toLowerCase();
  const type = browsers[name];
  if (!type) throw new Error(`Unknown BROWSER "${name}". Use chromium | firefox | webkit`);
  browser = await type.launch({
    headless: String(process.env.HEADLESS).toLowerCase() !== 'false',
  });
  logger.info(`Launched ${name} (headless=${process.env.HEADLESS}) | ENV=${process.env.ENV}`);
  fs.mkdirSync(TRACE_DIR, { recursive: true });
});

Before(async function (scenario) {
  const name = scenario.pickle.name;
  this.log = scenarioLogger(name);
  this.log.info(`--- Scenario started: ${name} ---`);

  const tags = scenario.pickle.tags.map((t) => t.name);
  this.isUiScenario = tags.includes('@ui');

  // Browser context only for UI scenarios — API/RAG runs stay lightweight
  if (this.isUiScenario) {
    this.context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      ...(process.env.VIDEO === 'on' ? { recordVideo: { dir: VIDEO_DIR } } : {}),
    });
    if (process.env.TRACE !== 'off') {
      await this.context.tracing.start({ screenshots: true, snapshots: true });
    }
    this.page = await this.context.newPage();
    this.page.setDefaultTimeout(Number(process.env.DEFAULT_TIMEOUT || 30000));
  }
});

/**
 * Per-step screenshots for UI scenarios so the report shows visual evidence
 * of every action/validation. STEP_SCREENSHOTS: on (default) | failure | off
 */
AfterStep(async function ({ pickleStep, result }) {
  const mode = (process.env.STEP_SCREENSHOTS || 'on').toLowerCase();
  if (mode === 'off' || !this.page) return;
  if (mode === 'failure' && result.status !== Status.FAILED) return;
  const png = await this.page
    .screenshot({ fullPage: false, animations: 'disabled' })
    .catch(() => null);
  if (png) this.attach(png, { mediaType: 'image/png', fileName: pickleStep.text });
});

After(async function (scenario) {
  const failed = scenario.result.status === Status.FAILED;

  if (this.page && failed) {
    const png = await this.page.screenshot({ fullPage: true }).catch(() => null);
    if (png) this.attach(png, 'image/png');
  }

  if (this.context) {
    if (process.env.TRACE !== 'off') {
      const keepTrace = failed || process.env.TRACE === 'on';
      const tracePath = path.join(TRACE_DIR, `${scenario.pickle.name.replace(/\W+/g, '_')}.zip`);
      await this.context.tracing.stop(keepTrace ? { path: tracePath } : {}).catch(() => {});
      if (keepTrace) this.log.info(`Trace saved: ${tracePath}`);
    }
    await this.context.close();
  }
  await this.api.dispose();

  (this.log || logger).info(`--- Scenario ${scenario.result.status}: ${scenario.pickle.name} ---`);
});

AfterAll(async function () {
  if (browser) await browser.close();
});
