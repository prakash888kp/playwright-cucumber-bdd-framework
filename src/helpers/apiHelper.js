/**
 * API helper — wraps Playwright's APIRequestContext with logging and
 * response capture so step definitions stay one-liners.
 */
const { request } = require('@playwright/test');
const { logger } = require('./logger');

class ApiHelper {
  constructor(baseURL) {
    this.baseURL = baseURL || process.env.API_BASE_URL;
    this.context = null;
    this.lastResponse = null;
    this.lastBody = null;
  }

  async init(extraHeaders = {}) {
    this.context = await request.newContext({
      baseURL: this.baseURL,
      extraHTTPHeaders: { 'Content-Type': 'application/json', ...extraHeaders },
    });
    return this;
  }

  async send(method, endpoint, { data, params, headers } = {}) {
    if (!this.context) await this.init();
    const started = Date.now();
    const response = await this.context.fetch(endpoint, {
      method: method.toUpperCase(),
      data,
      params,
      headers,
    });
    const elapsed = Date.now() - started;
    this.lastResponse = response;
    try {
      this.lastBody = await response.json();
    } catch {
      this.lastBody = await response.text();
    }
    logger.info(`API ${method.toUpperCase()} ${endpoint} -> ${response.status()} (${elapsed}ms)`);
    logger.debug(`API response body: ${JSON.stringify(this.lastBody).slice(0, 2000)}`);
    return response;
  }

  get(endpoint, opts) { return this.send('GET', endpoint, opts); }
  post(endpoint, data, opts = {}) { return this.send('POST', endpoint, { ...opts, data }); }
  put(endpoint, data, opts = {}) { return this.send('PUT', endpoint, { ...opts, data }); }
  patch(endpoint, data, opts = {}) { return this.send('PATCH', endpoint, { ...opts, data }); }
  delete(endpoint, opts) { return this.send('DELETE', endpoint, opts); }

  status() { return this.lastResponse ? this.lastResponse.status() : null; }
  body() { return this.lastBody; }

  /** Resolve a dotted path ("data.0.email") against the last response body. */
  bodyPath(dottedPath) {
    return dottedPath.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), this.lastBody);
  }

  async dispose() {
    if (this.context) await this.context.dispose();
  }
}

module.exports = { ApiHelper };
