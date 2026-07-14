/**
 * Custom Cucumber World — per-scenario container for browser page, API
 * helper, Bedrock helper, scenario logger and shared state.
 */
const { setWorldConstructor, setDefaultTimeout, World } = require('@cucumber/cucumber');
const { ApiHelper } = require('../helpers/apiHelper');
const { BedrockHelper } = require('../helpers/bedrockHelper');

setDefaultTimeout(Number(process.env.DEFAULT_TIMEOUT || 30000) * 2);

class CustomWorld extends World {
  constructor(options) {
    super(options);
    this.browser = null;   // set in hooks
    this.context = null;
    this.page = null;
    this.api = new ApiHelper();
    this.bedrock = new BedrockHelper();
    this.log = null;       // scenario-scoped winston logger, set in hooks
    this.data = {};        // scratch space to pass values between steps
    this.rag = {};         // { question, answer, citations } for RAG scenarios
  }
}

setWorldConstructor(CustomWorld);
module.exports = { CustomWorld };
