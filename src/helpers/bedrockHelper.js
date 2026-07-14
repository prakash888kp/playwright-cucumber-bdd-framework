/**
 * Amazon Bedrock helper — two capabilities used by RAG validation:
 *
 *  1. queryKnowledgeBase()  — RetrieveAndGenerate against a Bedrock Knowledge
 *     Base (the system under test for RAG scenarios).
 *  2. invokeJudge()         — invoke a Claude model as an LLM judge to score
 *     answer faithfulness/relevance against retrieved context.
 *
 * Credentials come from the standard AWS chain (env vars, profile, SSO).
 */
const {
  BedrockAgentRuntimeClient,
  RetrieveAndGenerateCommand,
  RetrieveCommand,
} = require('@aws-sdk/client-bedrock-agent-runtime');
const {
  BedrockRuntimeClient,
  InvokeModelCommand,
} = require('@aws-sdk/client-bedrock-runtime');
const { logger } = require('./logger');

class BedrockHelper {
  constructor() {
    const region = process.env.AWS_REGION || 'us-east-1';
    this.agentClient = new BedrockAgentRuntimeClient({ region });
    this.runtimeClient = new BedrockRuntimeClient({ region });
    this.kbId = process.env.BEDROCK_KB_ID;
    this.ragModelArn = process.env.BEDROCK_RAG_MODEL_ARN;
    this.judgeModelId = process.env.BEDROCK_JUDGE_MODEL_ID;
  }

  hasCredentials() {
    return Boolean(
      process.env.AWS_ACCESS_KEY_ID || process.env.AWS_PROFILE || process.env.AWS_ROLE_ARN
    );
  }

  /** Ask the Knowledge Base a question; returns { answer, citations[] }. */
  async queryKnowledgeBase(question, kbId = this.kbId) {
    if (!kbId) throw new Error('BEDROCK_KB_ID is not set');
    logger.info(`Bedrock RAG query: "${question}"`);
    const command = new RetrieveAndGenerateCommand({
      input: { text: question },
      retrieveAndGenerateConfiguration: {
        type: 'KNOWLEDGE_BASE',
        knowledgeBaseConfiguration: { knowledgeBaseId: kbId, modelArn: this.ragModelArn },
      },
    });
    const res = await this.agentClient.send(command);
    const answer = res.output?.text || '';
    const citations = (res.citations || []).flatMap((c) =>
      (c.retrievedReferences || []).map((r) => r.content?.text || '')
    );
    logger.debug(`Bedrock RAG answer: ${answer.slice(0, 500)}`);
    return { answer, citations };
  }

  /** Retrieve raw chunks only (no generation) — useful for retrieval-quality checks. */
  async retrieveChunks(question, kbId = this.kbId, topK = 5) {
    const command = new RetrieveCommand({
      knowledgeBaseId: kbId,
      retrievalQuery: { text: question },
      retrievalConfiguration: { vectorSearchConfiguration: { numberOfResults: topK } },
    });
    const res = await this.agentClient.send(command);
    return (res.retrievalResults || []).map((r) => ({
      text: r.content?.text || '',
      score: r.score,
    }));
  }

  /** LLM-as-judge: score an answer 0-10 for faithfulness + relevance. */
  async invokeJudge({ question, answer, context }) {
    const prompt = `You are a strict RAG evaluation judge.

Question: ${question}

Retrieved context:
${context}

Generated answer:
${answer}

Score the answer and reply ONLY with minified JSON:
{"faithfulness": <0-10, is every claim grounded in the context>, "relevance": <0-10, does it answer the question>, "verdict": "<PASS|FAIL>", "reason": "<one sentence>"}`;

    const command = new InvokeModelCommand({
      modelId: this.judgeModelId,
      contentType: 'application/json',
      accept: 'application/json',
      body: JSON.stringify({
        anthropic_version: 'bedrock-2023-05-31',
        max_tokens: 300,
        messages: [{ role: 'user', content: prompt }],
      }),
    });
    const res = await this.runtimeClient.send(command);
    const payload = JSON.parse(Buffer.from(res.body).toString('utf-8'));
    const text = payload.content?.[0]?.text || '{}';
    const match = text.match(/\{[\s\S]*\}/);
    const scores = JSON.parse(match ? match[0] : '{}');
    logger.info(`RAG judge scores: ${JSON.stringify(scores)}`);
    return scores;
  }
}

module.exports = { BedrockHelper };
