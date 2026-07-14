/**
 * BasePage — shared engine for all page objects.
 *
 *  - locate(descriptor): resolves selector descriptors from src/selectors/
 *    files into Playwright locators, keeping role/label-first priority.
 *  - Reusable, auto-logged action wrappers (click, fill, getText, ...) so
 *    page objects stay declarative and every interaction lands in the log.
 *
 * Playwright auto-waiting is relied on throughout — no arbitrary timeouts.
 */
const { expect } = require('@playwright/test');
const { logger } = require('../helpers/logger');

class BasePage {
  constructor(page, log = logger) {
    this.page = page;
    this.log = log;
  }

  // ---------- Locator resolution ----------

  /**
   * Resolve a selector descriptor into a Locator.
   * Accepts: string (css/xpath) | {role,name} | {label} | {placeholder}
   *          {text} | {testId} | {css} — optionally { ..., nth } or Locator passthrough.
   */
  locate(descriptor) {
    if (typeof descriptor === 'string') return this.page.locator(descriptor);
    if (descriptor?.constructor?.name === 'Locator') return descriptor;

    const { role, name, label, placeholder, text, testId, css, nth } = descriptor;
    let loc;
    if (role) loc = this.page.getByRole(role, name ? { name } : undefined);
    else if (label) loc = this.page.getByLabel(label);
    else if (placeholder) loc = this.page.getByPlaceholder(placeholder);
    else if (text) loc = this.page.getByText(text, { exact: descriptor.exact ?? false });
    else if (testId) loc = this.page.locator(`[data-test="${testId}"]`);
    else if (css) loc = this.page.locator(css);
    else throw new Error(`Unknown selector descriptor: ${JSON.stringify(descriptor)}`);

    return nth !== undefined ? loc.nth(nth) : loc;
  }

  describe(descriptor) {
    return typeof descriptor === 'string' ? descriptor : JSON.stringify(descriptor);
  }

  // ---------- Navigation ----------

  async open(pathname = '/') {
    const url = new URL(pathname, process.env.BASE_URL).href;
    this.log.info(`Navigate: ${url}`);
    await this.page.goto(url);
  }

  async waitForLoad(state = 'domcontentloaded') {
    await this.page.waitForLoadState(state);
  }

  async title() {
    return this.page.title();
  }

  // ---------- Actions (auto-logged) ----------

  async click(descriptor, elementName = '') {
    this.log.info(`Click: ${elementName || this.describe(descriptor)}`);
    await this.locate(descriptor).click();
  }

  async fill(descriptor, value, elementName = '', { mask = false } = {}) {
    this.log.info(`Fill: ${elementName || this.describe(descriptor)} = "${mask ? '******' : value}"`);
    await this.locate(descriptor).fill(String(value));
  }

  async selectByValue(descriptor, value, elementName = '') {
    this.log.info(`Select: ${elementName || this.describe(descriptor)} -> ${value}`);
    await this.locate(descriptor).selectOption(value);
  }

  async hover(descriptor, elementName = '') {
    this.log.info(`Hover: ${elementName || this.describe(descriptor)}`);
    await this.locate(descriptor).hover();
  }

  async press(descriptor, key, elementName = '') {
    this.log.info(`Press "${key}" on ${elementName || this.describe(descriptor)}`);
    await this.locate(descriptor).press(key);
  }

  // ---------- Reads ----------

  async getText(descriptor) {
    return (await this.locate(descriptor).textContent())?.trim();
  }

  async isVisible(descriptor) {
    return this.locate(descriptor).isVisible();
  }

  async count(descriptor) {
    return this.locate(descriptor).count();
  }

  // ---------- Assertions (auto-logged, auto-retrying via expect) ----------

  async expectVisible(descriptor, elementName = '') {
    this.log.info(`Assert visible: ${elementName || this.describe(descriptor)}`);
    await expect(this.locate(descriptor)).toBeVisible();
  }

  async expectText(descriptor, expected, elementName = '') {
    this.log.info(`Assert text: ${elementName || this.describe(descriptor)} = "${expected}"`);
    await expect(this.locate(descriptor)).toHaveText(expected);
  }

  async expectContainsText(descriptor, expected, elementName = '') {
    this.log.info(`Assert contains: ${elementName || this.describe(descriptor)} ~ "${expected}"`);
    await expect(this.locate(descriptor)).toContainText(expected);
  }

  async expectUrl(pattern) {
    this.log.info(`Assert URL matches: ${pattern}`);
    await expect(this.page).toHaveURL(pattern);
  }
}

module.exports = { BasePage };
