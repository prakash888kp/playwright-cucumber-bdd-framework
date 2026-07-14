const { BasePage } = require('./basePage');

class InventoryPage extends BasePage {
  constructor(page) {
    super(page);
    this.header = page.locator('.title');
    this.inventoryItems = page.locator('.inventory_item');
    this.cartBadge = page.locator('.shopping_cart_badge');
    this.sortDropdown = page.locator('[data-test="product-sort-container"]');
  }

  async addItemToCart(itemName) {
    const item = this.inventoryItems.filter({ hasText: itemName });
    await item.getByRole('button', { name: 'Add to cart' }).click();
  }

  async cartCount() {
    return (await this.cartBadge.isVisible()) ? Number(await this.cartBadge.textContent()) : 0;
  }
}

module.exports = { InventoryPage };
