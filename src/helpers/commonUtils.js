/**
 * Misc utilities — random data, dates, safe waits for the rare cases where
 * Playwright auto-waiting is not enough (e.g. polling an external system).
 */
const crypto = require('crypto');

const randomString = (len = 8) => crypto.randomBytes(len).toString('hex').slice(0, len);
const randomEmail = (domain = 'example.com') => `qa_${randomString(6)}@${domain}`;
const randomNumber = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

const todayISO = () => new Date().toISOString().slice(0, 10);
const timestamp = () => new Date().toISOString().replace(/[:.]/g, '-');

/** Poll an async predicate until true or timeout — for non-DOM waits only. */
async function waitUntil(predicate, { timeoutMs = 15000, intervalMs = 500, message = 'condition' } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Timed out after ${timeoutMs}ms waiting for ${message}`);
}

module.exports = { randomString, randomEmail, randomNumber, todayISO, timestamp, waitUntil };
