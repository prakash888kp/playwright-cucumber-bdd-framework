"""RAG validation strategies — deterministic (keyword coverage, citation
presence) plus LLM-as-judge via Bedrock. Thresholds are env-tunable.
"""
import os
import re

from .logger import logger


def keyword_coverage(answer: str, expected_keywords) -> dict:
    """% of expected keywords present in the answer (case-insensitive)."""
    keywords = [k.strip().lower() for k in re.split(r"[;,|]", str(expected_keywords)) if k.strip()]
    if not keywords:
        return {"coverage": 1.0, "missing": []}
    haystack = answer.lower()
    missing = [k for k in keywords if k not in haystack]
    coverage = (len(keywords) - len(missing)) / len(keywords)
    logger.info(
        f"RAG keyword coverage: {coverage * 100:.0f}% (missing: {', '.join(missing) or 'none'})"
    )
    return {"coverage": coverage, "missing": missing}


def assert_keyword_coverage(answer: str, expected_keywords):
    minimum = float(os.environ.get("RAG_MIN_KEYWORD_COVERAGE", 0.6))
    result = keyword_coverage(answer, expected_keywords)
    if result["coverage"] < minimum:
        raise AssertionError(
            f"RAG keyword coverage {result['coverage'] * 100:.0f}% below threshold "
            f"{minimum * 100:.0f}%. Missing: {', '.join(result['missing'])}"
        )


def assert_has_citations(citations):
    if not citations:
        raise AssertionError("RAG answer returned no citations — answer may be hallucinated")


def assert_judge_verdict(bedrock, question: str, answer: str, context: str) -> dict:
    min_score = float(os.environ.get("RAG_MIN_JUDGE_SCORE", 7))
    scores = bedrock.invoke_judge(question, answer, context)
    if (
        scores.get("verdict") != "PASS"
        or scores.get("faithfulness", 0) < min_score
        or scores.get("relevance", 0) < min_score
    ):
        raise AssertionError(f"LLM judge failed the answer: {scores} (min score {min_score})")
    return scores
