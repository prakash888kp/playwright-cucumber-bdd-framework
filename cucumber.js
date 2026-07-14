/**
 * Cucumber profiles — the single source of truth for test execution config.
 *
 * Run modes:
 *  1. Excel-driven : npm run test:excel        (reads config/execution-control.xlsx)
 *  2. Env-driven   : npm run test:env          (reads TAGS/BROWSER/etc from config/env/.env.<ENV>)
 *  3. CLI-driven   : npm test -- --tags "@smoke"
 */
const { loadEnv } = require('./src/config/envLoader');
loadEnv();

const parallel = Number(process.env.PARALLEL || 1);
const retry = Number(process.env.RETRY || 0);
const tags = process.env.TAGS || '';

const common = {
  paths: ['src/features/**/*.feature'],
  require: ['src/support/**/*.js', 'src/steps/**/*.js'],
  format: [
    'progress-bar',
    'json:reports/cucumber-report.json',
    'html:reports/cucumber-report.html',
    'rerun:reports/@rerun.txt',
  ],
  formatOptions: { snippetInterface: 'async-await' },
  parallel,
  retry,
  ...(tags ? { tags } : {}),
};

module.exports = {
  default: common,
  smoke: { ...common, tags: '@smoke' },
  regression: { ...common, tags: '@regression' },
  ui: { ...common, tags: '@ui' },
  api: { ...common, tags: '@api' },
  rag: { ...common, tags: '@rag' },
  rerun: { ...common, paths: ['reports/@rerun.txt'] },
};
