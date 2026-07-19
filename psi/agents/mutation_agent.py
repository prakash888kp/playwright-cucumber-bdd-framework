"""Mutation Agent — generates variations and edge cases.

Fills the gaps the Coverage Agent flagged. For an API happy-path it appends a
negative edge case (a non-existent resource) as an additional case. The
Self-Healing Agent later calibrates the expected status against reality, so the
mutation only has to propose the interesting *input* — it need not be certain of
the exact status code.
"""
from __future__ import annotations

import re

from ..models import Requirement
from .base import BaseAgent


class MutationAgent(BaseAgent):
    name = "mutation-agent"
    role = "Generates variations / edge cases"

    def run(self, req: Requirement, plan: dict):
        added = 0
        if plan["type"] == "api" and "negative-case" in plan.get("gaps", []):
            base = plan["cases"][0]
            if base.get("method", "GET").upper() == "GET" and "/users/" in base.get("endpoint", ""):
                # Same collection, an id that won't exist -> a not-found edge case.
                neg_endpoint = re.sub(r"/(\d+)$", "/99999999", base["endpoint"])
                if neg_endpoint == base["endpoint"]:
                    neg_endpoint = base["endpoint"].rstrip("/") + "/99999999"
                plan["cases"].append(
                    {
                        "tc_id": f"{plan['scenario_id']}_M1",
                        "name": f"{plan['scenario_name']} - not found edge case",
                        "method": "GET",
                        "endpoint": neg_endpoint,
                        "expected_status": 404,   # best guess; healing calibrates if wrong
                        "assert_field": None,     # negative case asserts status only
                        "negative": True,
                    }
                )
                added = 1
        return self._result(f"{added} edge case(s) added")
