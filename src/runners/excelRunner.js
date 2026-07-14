/**
 * Run mode 1 — Excel-driven execution.
 *
 * Reads config/execution-control.xlsx (sheet "ExecutionControl"), collects the
 * scenario IDs where Run = YES, builds a cucumber tag expression, and spawns
 * cucumber-js. Any extra CLI args are forwarded, e.g.:
 *
 *   node src/runners/excelRunner.js            # run everything flagged YES
 *   node src/runners/excelRunner.js --parallel 4
 */
const path = require('path');
const { readSheet } = require('../helpers/excelReader');
const { logger } = require('../helpers/logger');

const ROOT = path.resolve(__dirname, '..', '..');
const { runAndReport } = require(path.join(ROOT, 'scripts', 'run.js'));
const CONTROL_FILE = path.join(ROOT, 'config', 'execution-control.xlsx');

const rows = readSheet(CONTROL_FILE, 'ExecutionControl');
const selected = rows.filter((r) => String(r.Run).trim().toUpperCase() === 'YES');

if (!selected.length) {
  logger.error('No scenarios flagged Run=YES in execution-control.xlsx — nothing to run.');
  process.exit(1);
}

logger.info('Execution plan from Excel:');
selected.forEach((r) => logger.info(`  [YES] ${r.ScenarioID} — ${r.ScenarioName}`));
const skipped = rows.length - selected.length;
if (skipped) logger.info(`  (${skipped} scenario(s) flagged NO — skipped)`);

const tagExpression = selected.map((r) => `@${String(r.ScenarioID).trim()}`).join(' or ');
logger.info(`Tag expression: ${tagExpression}`);

runAndReport(['--tags', tagExpression, ...process.argv.slice(2)]).then((code) =>
  process.exit(code)
);
