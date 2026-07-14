/**
 * Manual report build — normally unnecessary because every run (npm test,
 * test:excel, profiles) auto-generates a timestamped archive via scripts/run.js.
 * Use this only to rebuild a report from the last cucumber-report.json.
 */
const { loadEnv } = require('../src/config/envLoader');
loadEnv();
const { buildReport } = require('../src/helpers/reportBuilder');

buildReport().then((result) => {
  if (!result) process.exit(1);
});
