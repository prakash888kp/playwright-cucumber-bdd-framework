const { Given, When, Then } = require('@cucumber/cucumber');
const assert = require('node:assert/strict');
const dataManager = require('../../helpers/dataManager');

Given('I load API data for {string}', async function (tcId) {
  this.data.api = dataManager.getData('APIData', tcId);
  this.log.info(`Loaded API data for ${tcId}: ${this.data.api.Method} ${this.data.api.Endpoint}`);
});

When('I send a GET request to the endpoint from test data', async function () {
  await this.api.get(this.data.api.Endpoint);
});

When('I send a POST request with the payload from test data', async function () {
  const payload = JSON.parse(this.data.api.Payload || '{}');
  await this.api.post(this.data.api.Endpoint, payload);
});

Then('the response status should match the expected status', async function () {
  const expected = Number(this.data.api.ExpectedStatus);
  assert.equal(this.api.status(), expected, `Expected HTTP ${expected}, got ${this.api.status()}`);
  this.log.info(`Status ${expected} verified`);
});

Then('the response field {string} should not be empty', async function (fieldPath) {
  const value = this.api.bodyPath(fieldPath);
  assert.ok(
    value !== undefined && value !== null && value !== '',
    `Response field "${fieldPath}" is empty. Body: ${JSON.stringify(this.api.body()).slice(0, 500)}`
  );
  this.log.info(`Field "${fieldPath}" = ${JSON.stringify(value)}`);
});

Then('the response field {string} should equal {string}', async function (fieldPath, expected) {
  const value = this.api.bodyPath(fieldPath);
  assert.equal(String(value), expected);
});
