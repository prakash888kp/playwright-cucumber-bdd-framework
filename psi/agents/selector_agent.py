"""Selector Agent — finds stable locators for UI journeys.

For API scenarios there is no DOM, so it records that and steps aside. For UI
scenarios it proposes descriptor-style selectors (the framework's role/testId/
css dicts) — from Bedrock when available, otherwise resilient placeholders the
human refines. In the full vision this agent parses the live DOM on Fargate.
"""
from __future__ import annotations

from ..models import Requirement
from .base import BaseAgent


class SelectorAgent(BaseAgent):
    name = "selector-agent"
    role = "DOM parser + finds stable locators"

    def run(self, req: Requirement, plan: dict):
        if plan["type"] != "ui":
            plan.setdefault("selectors", {})
            return self._result("no DOM for API scenario — skipped")

        if self.llm.available():
            system = (
                "You are the Selector Agent. Propose Playwright-friendly selectors as "
                "JSON mapping UPPER_SNAKE names to descriptor objects using keys among "
                "role,name,placeholder,testId,css. Prefer role/testId over css."
            )
            plan["selectors"] = self.llm.json(system, req.text) or {}
        else:
            plan["selectors"] = {
                "PAGE_HEADER": {"css": ".title"},
                "PRIMARY_ACTION": {"role": "button", "name": "Submit"},
            }
        return self._result(f"{len(plan['selectors'])} selector(s) proposed")
