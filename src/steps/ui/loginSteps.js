const { Given, When, Then } = require('@cucumber/cucumber');
const dataManager = require('../../helpers/dataManager');

Given('I load login data for {string}', async function (tcId) {
  this.data.login = dataManager.getData('LoginData', tcId);
  this.log.info(`Loaded login data for ${tcId} (user: ${this.data.login.Username})`);
});

When('I login with the loaded credentials', async function () {
  await this.pages.loginPage.goto();
  await this.pages.loginPage.login(this.data.login.Username, this.data.login.Password);
});

Then('I should land on the inventory page', async function () {
  await this.pages.inventoryPage.verifyLoaded();
});

Then('I should see the login error from test data', async function () {
  await this.pages.loginPage.verifyError(this.data.login.ExpectedError);
});
