"""RAG validation steps — Bedrock Knowledge Base + deterministic/LLM-judge checks.
Unconfigured machines skip via before_scenario in environment.py.
"""
import json
import os

from behave import step

from framework.helpers import data_manager
from framework.support.attachments import attach_text
from framework.helpers.rag_validator import (
    assert_has_citations,
    assert_judge_verdict,
    assert_keyword_coverage,
)


@step('I load RAG data for "{tc_id}"')
def load_rag_data(context, tc_id):
    context.data["rag"] = data_manager.get_data("RAGData", tc_id)
    context.log.info(f"Loaded RAG data for {tc_id}: \"{context.data['rag']['Question']}\"")


@step("I query the Bedrock knowledge base with the question from test data")
def query_knowledge_base(context):
    row = context.data["rag"]
    kb_id = row.get("KnowledgeBaseId") or os.environ.get("BEDROCK_KB_ID")
    context.rag = context.bedrock.query_knowledge_base(row["Question"], kb_id)
    attach_text(context, "Q & A", f"Question: {row['Question']}\n\nAnswer: {context.rag['answer']}")


@step("the RAG answer should contain the expected keywords")
def rag_answer_keywords(context):
    assert_keyword_coverage(context.rag["answer"], context.data["rag"]["ExpectedKeywords"])


@step("the RAG answer should include citations")
def rag_answer_citations(context):
    assert_has_citations(context.rag["citations"])
    context.log.info(f"Citations found: {len(context.rag['citations'])}")


@step("the RAG answer should pass the LLM judge evaluation")
def rag_answer_judge(context):
    scores = assert_judge_verdict(
        context.bedrock,
        question=context.data["rag"]["Question"],
        answer=context.rag["answer"],
        context="\n---\n".join(context.rag["citations"]),
    )
    attach_text(context, "Judge scores", json.dumps(scores, indent=2))
