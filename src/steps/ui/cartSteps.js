const { When, Then } = require('@cucumber/cucumber');
const { expect } = require('@playwright/test');
const { InventoryPage } = require('../../pages/inventoryPage');
const dataManager = require('../../helpers/dataManager');

When('I add product for {string} to the cart', async function (tcId) {
  const row = dataManager.getData('CartData', tcId);
  const inventoryPage = new InventoryPage(this.page);
  await inventoryPage.addItemToCart(row.ProductName);
  this.log.info(`Added "${row.ProductName}" to cart`);
});

Then('the cart badge should show {int} item(s)', async function (count) {
  const inventoryPage = new InventoryPage(this.page);
  await expect(inventoryPage.cartBadge).toHaveText(String(count));
});
