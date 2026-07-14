const { BasePage } = require('./basePage');
const SEL = require('../selectors/inventorySelectors');

class InventoryPage extends BasePage {
  async verifyLoaded() {
    await this.expectUrl(/inventory\.html/);
    await this.expectText(SEL.PAGE_HEADER, 'Products', 'Page header');
  }

  async addItemToCart(itemName) {
    const item = this.locate(SEL.INVENTORY_ITEM).filter({ hasText: itemName });
    this.log.info(`Add to cart: "${itemName}"`);
    await item.getByRole('button', { name: 'Add to cart' }).click();
  }

  async verifyCartCount(count) {
    await this.expectText(SEL.CART_BADGE, String(count), 'Cart badge');
  }

  async sortBy(value) {
    await this.selectByValue(SEL.SORT_DROPDOWN, value, 'Sort dropdown');
  }
}

module.exports = { InventoryPage };
