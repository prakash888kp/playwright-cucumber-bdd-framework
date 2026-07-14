/**
 * Environment loader — merges (in priority order):
 *   1. Real process env / CLI            (highest — cross-env or shell exports win)
 *   2. config/env/.env.<ENV>             (environment-specific values)
 *   3. .env at project root              (defaults)
 */
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');

function loadEnv() {
  const root = path.resolve(__dirname, '..', '..');

  // Root defaults first (does not overwrite anything already set)
  dotenv.config({ path: path.join(root, '.env') });

  const env = (process.env.ENV || 'qa').toLowerCase();
  const envFile = path.join(root, 'config', 'env', `.env.${env}`);
  if (fs.existsSync(envFile)) {
    dotenv.config({ path: envFile });
  }
  process.env.ENV = env;
  return process.env;
}

module.exports = { loadEnv };
