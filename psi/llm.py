"""LLM access for the agents — pluggable provider, with an offline fallback.

Providers (auto-detected, or forced via PSI_LLM_PROVIDER):
  * "anthropic" — the Claude API via the official `anthropic` SDK. Works from
    Claude Code, Claude Desktop, or any host with ANTHROPIC_API_KEY (or an
    `ant auth login` profile). Default model: claude-opus-4-8.
  * "bedrock"   — Claude on Amazon Bedrock via boto3 (AWS-native deployments).
  * "offline"   — no model; agents fall back to deterministic heuristics so the
    pipeline still runs (and self-verifies) with no cloud access.

Auto-detection order: ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN -> AWS creds ->
offline. Set PSI_LLM_PROVIDER=anthropic|bedrock|offline to override.
"""
from __future__ import annotations

import json
import os
import re


class LLM:
    def __init__(self) -> None:
        self.provider = (os.environ.get("PSI_LLM_PROVIDER") or self._auto_provider()).lower()
        # Claude API uses bare model IDs; Bedrock uses the anthropic.-prefixed IDs.
        self.anthropic_model = os.environ.get("PSI_ANTHROPIC_MODEL", "claude-opus-4-8")
        self.bedrock_model = os.environ.get(
            "PSI_BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self._client = None

    # -- provider selection -------------------------------------------------
    @staticmethod
    def _has_aws() -> bool:
        return bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_ROLE_ARN")
        )

    @classmethod
    def _auto_provider(cls) -> str:
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return "anthropic"
        if cls._has_aws():
            return "bedrock"
        return "offline"

    def available(self) -> bool:
        return self.provider in ("anthropic", "bedrock")

    @property
    def model(self) -> str:
        return self.anthropic_model if self.provider == "anthropic" else self.bedrock_model

    # -- lazy provider client ----------------------------------------------
    @property
    def client(self):
        if self._client is None:
            if self.provider == "anthropic":
                import anthropic

                # Resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile.
                self._client = anthropic.Anthropic()
            else:
                import boto3

                self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    # -- completion --------------------------------------------------------
    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        """Single-turn completion. Callers guard with available() first."""
        if self.provider == "anthropic":
            return self._complete_anthropic(system, prompt, max_tokens)
        return self._complete_bedrock(system, prompt, max_tokens)

    def _complete_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        resp = self.client.messages.create(
            model=self.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def _complete_bedrock(self, system: str, prompt: str, max_tokens: int) -> str:
        resp = self.client.invoke_model(
            modelId=self.bedrock_model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )
        payload = json.loads(resp["body"].read())
        return (payload.get("content") or [{}])[0].get("text", "")

    def json(self, system: str, prompt: str, max_tokens: int = 1500) -> dict:
        """Completion that must return a JSON object; tolerant of prose around it."""
        text = self.complete(system, prompt, max_tokens)
        match = re.search(r"\{[\s\S]*\}", text)
        return json.loads(match.group(0)) if match else {}
