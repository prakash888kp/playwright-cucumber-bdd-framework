const { Given, When, Then } = require('@cucumber/cucumber');
const { expect } = require('@playwright/test');
const { LoginPage } = require('../../pages/loginPage');
const { InventoryPage } = require('../../pages/inventoryPage');
const dataManager = require('../../helpers/dataManager');

Given('I load login data for {string}', async function (tcId) {
  this.data.login = dataManager.getData('LoginData', tcId);
  this.log.info(`Loaded login data for ${tcId} (user: ${this.data.login.Username})`);
});

When('I login with the loaded credentials', async function () {
  const loginPage = new LoginPage(this.page);
  await loginPage.goto();
  await loginPage.login(this.data.login.Username, this.data.login.Password);
  this.log.info('Submitted login form');
});

Then('I should land on the inventory page', async function () {
  const inventoryPage = new InventoryPage(this.page);
  await expect(this.page).toHaveURL(/inventory\.html/);
  await expect(inventoryPage.header).toHaveText('Products');
  this.log.info('Inventory page verified');
});

Then('I should see the login error from test data', async function () {
  const loginPage = new LoginPage(this.page);
  await expect(loginPage.errorMessage).toBeVisible();
  await expect(loginPage.errorMessage).toContainText(this.data.login.ExpectedError);
  this.log.info(`Login error verified: "${this.data.login.ExpectedError}"`);
});
