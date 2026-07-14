/**
 * RAG validation strategies — deterministic (keyword coverage, citation
 * presence) plus LLM-as-judge via Bedrock. Thresholds are env-tunable.
 */
const { logger } = require('./logger');

/** % of expected keywords present in the answer (case-insensitive). */
function keywordCoverage(answer, expectedKeywords) {
  const keywords = String(expectedKeywords)
    .split(/[;,|]/)
    .map((k) => k.trim().toLowerCase())
    .filter(Boolean);
  if (!keywords.length) return { coverage: 1, missing: [] };
  const haystack = answer.toLowerCase();
  const missing = keywords.filter((k) => !haystack.includes(k));
  const coverage = (keywords.length - missing.length) / keywords.length;
  logger.info(`RAG keyword coverage: ${(coverage * 100).toFixed(0)}% (missing: ${missing.join(', ') || 'none'})`);
  return { coverage, missing };
}

function assertKeywordCoverage(answer, expectedKeywords) {
  const min = Number(process.env.RAG_MIN_KEYWORD_COVERAGE || 0.6);
  const { coverage, missing } = keywordCoverage(answer, expectedKeywords);
  if (coverage < min) {
    throw new Error(
      `RAG keyword coverage ${(coverage * 100).toFixed(0)}% below threshold ${min * 100}%. Missing: ${missing.join(', ')}`
    );
  }
}

function assertHasCitations(citations) {
  if (!citations || citations.length === 0) {
    throw new Error('RAG answer returned no citations — answer may be hallucinated');
  }
}

async function assertJudgeVerdict(bedrock, { question, answer, context }) {
  const minScore = Number(process.env.RAG_MIN_JUDGE_SCORE || 7);
  const scores = await bedrock.invokeJudge({ question, answer, context });
  if (scores.verdict !== 'PASS' || scores.faithfulness < minScore || scores.relevance < minScore) {
    throw new Error(
      `LLM judge failed the answer: ${JSON.stringify(scores)} (min score ${minScore})`
    );
  }
  return scores;
}

module.exports = { keywordCoverage, assertKeywordCoverage, assertHasCitations, assertJudgeVerdict };
