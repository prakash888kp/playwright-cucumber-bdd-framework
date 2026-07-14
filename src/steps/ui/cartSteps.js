const { When, Then } = require('@cucumber/cucumber');
const dataManager = require('../../helpers/dataManager');

When('I add product for {string} to the cart', async function (tcId) {
  const row = dataManager.getData('CartData', tcId);
  await this.pages.inventoryPage.addItemToCart(row.ProductName);
});

Then('the cart badge should show {int} item(s)', async function (count) {
  await this.pages.inventoryPage.verifyCartCount(count);
});
