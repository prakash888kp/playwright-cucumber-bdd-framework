"""Flow Agent — discovers the user journey and shapes the base scenario.

Turns a plain-language requirement into a structured plan: test type (ui/api),
a stable scenario id, feature/scenario names, and a `cases` list whose first
entry is the base case (the Mutation Agent appends edge cases later). Uses
Bedrock/Claude when available; otherwise a deterministic heuristic.
"""
from __future__ import annotations

import hashlib
import re

from ..models import Requirement
from .base import BaseAgent

_UI_HINTS = ("login", "click", "page", "button", "cart", "form", "navigate", "screen")
_API_HINTS = ("api", "endpoint", "response", "status", "payload", "get ", "post ", "user")


def _scenario_id(req: Requirement) -> str:
    seed = f"{req.ticket_id}|{req.text}".encode()
    return "TC_GEN_" + hashlib.sha1(seed).hexdigest()[:6].upper()


class FlowAgent(BaseAgent):
    name = "flow-agent"
    role = "Discovers user journeys"

    def run(self, req: Requirement, plan: dict):
        plan["scenario_id"] = _scenario_id(req)

        if self.llm.available():
            self._plan_with_llm(req, plan)
        else:
            self._plan_heuristic(req, plan)

        # The base case (mutations get appended by the Mutation Agent).
        base = {
            "tc_id": plan["scenario_id"],
            "name": plan["scenario_name"],
            "method": plan["method"],
            "endpoint": plan["endpoint"],
            "expected_status": plan["expected_status"],
            "assert_field": plan["assert_field"],
            "negative": False,
        }
        plan["cases"] = [base]
        return self._result(
            f"type={plan['type']} scenario={plan['scenario_id']} "
            + (f"({plan['method']} {plan['endpoint']})" if plan["type"] == "api" else "")
        )

    def _plan_with_llm(self, req: Requirement, plan: dict) -> None:
        system = (
            "You are the Flow Agent in a test-generation swarm. Given a requirement and the "
            "reusable framework context, return JSON: {type:'ui'|'api', feature_name, "
            "scenario_name, method, endpoint, expected_status, assert_field}."
        )
        prompt = f"{plan.get('kg_context', '')}\n\nRequirement: {req.text}"
        data = self.llm.json(system, prompt) or {}
        plan["type"] = (data.get("type") or self._detect_type(req.text)).lower()
        plan["feature_name"] = data.get("feature_name") or self._title(req.text)
        plan["scenario_name"] = data.get("scenario_name") or f"Verify {self._title(req.text)}"
        plan["method"] = (data.get("method") or "GET").upper()
        plan["endpoint"] = data.get("endpoint") or self._endpoint(req.text)
        plan["expected_status"] = int(data.get("expected_status") or 200)
        plan["assert_field"] = data.get("assert_field") or "name"

    def _plan_heuristic(self, req: Requirement, plan: dict) -> None:
        plan["type"] = self._detect_type(req.text)
        plan["feature_name"] = self._title(req.text)
        plan["scenario_name"] = f"Verify {self._title(req.text)}"
        plan["method"] = "GET"
        plan["endpoint"] = self._endpoint(req.text)
        plan["expected_status"] = 200
        plan["assert_field"] = "name"

    @staticmethod
    def _detect_type(text: str) -> str:
        low = text.lower()
        api = sum(h in low for h in _API_HINTS)
        ui = sum(h in low for h in _UI_HINTS)
        return "ui" if ui > api else "api"

    @staticmethod
    def _endpoint(text: str) -> str:
        m = re.search(r"\b(\d{1,6})\b", text)
        return f"/users/{m.group(1) if m else '1'}"

    @staticmethod
    def _title(text: str) -> str:
        first = text.strip().splitlines()[0]
        return (first[:60] + "...") if len(first) > 60 else first
