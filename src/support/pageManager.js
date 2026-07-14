/**
 * PageManager — lazy page-object factory, one per scenario.
 * Steps never `new` a page: use `this.pages.loginPage` etc. Instances are
 * created on first access, cached for the scenario, and share the
 * scenario-scoped logger so page actions appear under the scenario label.
 *
 * Adding a page: import it and add one getter.
 */
const { LoginPage } = require('../pages/loginPage');
const { InventoryPage } = require('../pages/inventoryPage');

class PageManager {
  constructor(page, log) {
    this.page = page;
    this.log = log;
    this._cache = new Map();
  }

  _get(name, Ctor) {
    if (!this._cache.has(name)) this._cache.set(name, new Ctor(this.page, this.log));
    return this._cache.get(name);
  }

  get loginPage() { return this._get('loginPage', LoginPage); }
  get inventoryPage() { return this._get('inventoryPage', InventoryPage); }
}

module.exports = { PageManager };
