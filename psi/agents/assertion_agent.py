"""Assertion Agent — defines the validation logic (the Then steps).

Decides what "correct" means for the scenario. For API it picks the status code
and a response field that must be present; for UI it names the visible outcome
to assert. Bedrock refines these; the offline default is a sensible check.
"""
from __future__ import annotations

from ..models import Requirement
from .base import BaseAgent


class AssertionAgent(BaseAgent):
    name = "assertion-agent"
    role = "Defines validation logic"

    def run(self, req: Requirement, plan: dict):
        if plan["type"] == "api":
            plan.setdefault("expected_status", 200)
            plan.setdefault("assert_field", "name")
            return self._result(
                f"assert status {plan['expected_status']} and field "
                f"'{plan['assert_field']}' not empty"
            )

        if self.llm.available():
            system = (
                "You are the Assertion Agent. Return JSON {outcome: '<short visible "
                "result to assert>'} for the requirement."
            )
            outcome = (self.llm.json(system, req.text) or {}).get("outcome")
            plan["ui_outcome"] = outcome or "the expected result is visible"
        else:
            plan["ui_outcome"] = "the expected result is visible"
        return self._result(f"assert: {plan['ui_outcome']}")
