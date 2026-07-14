"""Amazon Bedrock helper — two capabilities used by RAG validation:

 1. query_knowledge_base() — RetrieveAndGenerate against a Bedrock Knowledge
    Base (the system under test for RAG scenarios).
 2. invoke_judge()         — invoke a Claude model as an LLM judge to score
    answer faithfulness/relevance against retrieved context.

Credentials come from the standard AWS chain (env vars, profile, SSO).
Clients are created lazily so unconfigured machines never touch boto3.
"""
import json
import os
import re

import boto3

from .logger import logger


class BedrockHelper:
    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.kb_id = os.environ.get("BEDROCK_KB_ID")
        self.rag_model_arn = os.environ.get("BEDROCK_RAG_MODEL_ARN")
        self.judge_model_id = os.environ.get("BEDROCK_JUDGE_MODEL_ID")
        self._agent_client = None
        self._runtime_client = None

    @property
    def agent_client(self):
        if self._agent_client is None:
            self._agent_client = boto3.client("bedrock-agent-runtime", region_name=self.region)
        return self._agent_client

    @property
    def runtime_client(self):
        if self._runtime_client is None:
            self._runtime_client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._runtime_client

    def has_credentials(self) -> bool:
        return bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_ROLE_ARN")
        )

    def query_knowledge_base(self, question: str, kb_id: str | None = None) -> dict:
        """Ask the Knowledge Base a question; returns {"answer", "citations"}."""
        kb_id = kb_id or self.kb_id
        if not kb_id:
            raise RuntimeError("BEDROCK_KB_ID is not set")
        logger.info(f'Bedrock RAG query: "{question}"')
        res = self.agent_client.retrieve_and_generate(
            input={"text": question},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": kb_id,
                    "modelArn": self.rag_model_arn,
                },
            },
        )
        answer = (res.get("output") or {}).get("text", "")
        citations = [
            (ref.get("content") or {}).get("text", "")
            for c in res.get("citations", [])
            for ref in c.get("retrievedReferences", [])
        ]
        logger.debug(f"Bedrock RAG answer: {answer[:500]}")
        return {"answer": answer, "citations": citations}

    def retrieve_chunks(self, question: str, kb_id: str | None = None, top_k: int = 5) -> list[dict]:
        """Retrieve raw chunks only (no generation) — for retrieval-quality checks."""
        res = self.agent_client.retrieve(
            knowledgeBaseId=kb_id or self.kb_id,
            retrievalQuery={"text": question},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": top_k}},
        )
        return [
            {"text": (r.get("content") or {}).get("text", ""), "score": r.get("score")}
            for r in res.get("retrievalResults", [])
        ]

    def invoke_judge(self, question: str, answer: str, context: str) -> dict:
        """LLM-as-judge: score an answer 0-10 for faithfulness + relevance."""
        prompt = f"""You are a strict RAG evaluation judge.

Question: {question}

Retrieved context:
{context}

Generated answer:
{answer}

Score the answer and reply ONLY with minified JSON:
{{"faithfulness": <0-10, is every claim grounded in the context>, "relevance": <0-10, does it answer the question>, "verdict": "<PASS|FAIL>", "reason": "<one sentence>"}}"""

        res = self.runtime_client.invoke_model(
            modelId=self.judge_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )
        payload = json.loads(res["body"].read())
        text = (payload.get("content") or [{}])[0].get("text", "{}")
        match = re.search(r"\{[\s\S]*\}", text)
        scores = json.loads(match.group(0) if match else "{}")
        logger.info(f"RAG judge scores: {json.dumps(scores)}")
        return scores
