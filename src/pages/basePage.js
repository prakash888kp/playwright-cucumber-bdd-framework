/**
 * BasePage — shared behaviour for all page objects.
 */
class BasePage {
  constructor(page) {
    this.page = page;
  }

  async open(pathname = '/') {
    await this.page.goto(new URL(pathname, process.env.BASE_URL).href);
  }

  async title() {
    return this.page.title();
  }
}

module.exports = { BasePage };
