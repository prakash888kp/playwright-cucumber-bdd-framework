const { Given, When, Then, Before } = require('@cucumber/cucumber');
const dataManager = require('../../helpers/dataManager');
const { logger } = require('../../helpers/logger');
const {
  assertKeywordCoverage,
  assertHasCitations,
  assertJudgeVerdict,
} = require('../../helpers/ragValidator');

// Skip RAG scenarios gracefully when AWS credentials / KB are not configured,
// so the suite stays green on machines without Bedrock access.
Before({ tags: '@rag' }, async function () {
  if (!this.bedrock.hasCredentials() || !process.env.BEDROCK_KB_ID) {
    logger.warn('Skipping RAG scenario — AWS credentials or BEDROCK_KB_ID not configured');
    return 'skipped';
  }
});

Given('I load RAG data for {string}', async function (tcId) {
  this.data.rag = dataManager.getData('RAGData', tcId);
  this.log.info(`Loaded RAG data for ${tcId}: "${this.data.rag.Question}"`);
});

When('I query the Bedrock knowledge base with the question from test data', async function () {
  const { Question, KnowledgeBaseId } = this.data.rag;
  const kbId = KnowledgeBaseId || process.env.BEDROCK_KB_ID;
  this.rag = await this.bedrock.queryKnowledgeBase(Question, kbId);
  this.attach(`Question: ${Question}\n\nAnswer: ${this.rag.answer}`, 'text/plain');
});

Then('the RAG answer should contain the expected keywords', async function () {
  assertKeywordCoverage(this.rag.answer, this.data.rag.ExpectedKeywords);
});

Then('the RAG answer should include citations', async function () {
  assertHasCitations(this.rag.citations);
  this.log.info(`Citations found: ${this.rag.citations.length}`);
});

Then('the RAG answer should pass the LLM judge evaluation', async function () {
  const scores = await assertJudgeVerdict(this.bedrock, {
    question: this.data.rag.Question,
    answer: this.rag.answer,
    context: this.rag.citations.join('\n---\n'),
  });
  this.attach(`Judge scores: ${JSON.stringify(scores, null, 2)}`, 'text/plain');
});
