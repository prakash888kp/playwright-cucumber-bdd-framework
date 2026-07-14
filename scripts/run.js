/**
 * Universal runner — every run mode funnels through here so a timestamped
 * report archive is ALWAYS produced, pass or fail.
 *
 *   node scripts/run.js --tags "@smoke"
 *   node scripts/run.js --profile regression
 *
 * Exits with cucumber's exit code so CI still fails on test failures.
 */
const path = require('path');
const { spawnSync } = require('child_process');
const { loadEnv } = require('../src/config/envLoader');
loadEnv();

const ROOT = path.resolve(__dirname, '..');

function runCucumber(args = []) {
  const cucumberBin = path.join(ROOT, 'node_modules', '@cucumber', 'cucumber', 'bin', 'cucumber.js');
  const result = spawnSync(process.execPath, [cucumberBin, ...args], {
    stdio: 'inherit',
    cwd: ROOT,
  });
  return result.status ?? 1;
}

async function runAndReport(args = []) {
  process.env.RUN_ARGS = args.join(' ');
  const exitCode = runCucumber(args);
  const { buildReport } = require('../src/helpers/reportBuilder');
  await buildReport().catch((err) => console.error(`Report generation failed: ${err.message}`));
  return exitCode;
}

if (require.main === module) {
  runAndReport(process.argv.slice(2)).then((code) => process.exit(code));
}

module.exports = { runAndReport };
