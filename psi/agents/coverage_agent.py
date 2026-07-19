"""Coverage Agent — graph-diff logic; identifies what's missing.

Consults the Knowledge Graph to see what the framework already covers, whether
this requirement's endpoint is already tested, and what gaps remain (e.g. no
negative/edge case for this endpoint yet). The gaps it finds drive the Mutation
Agent, and the duplicate signal drives the Optimizer's reuse decision.
"""
from __future__ import annotations

from ..models import Requirement
from .base import BaseAgent


class CoverageAgent(BaseAgent):
    name = "coverage-agent"
    role = "Graph diff logic + identifies gaps"

    def run(self, req: Requirement, plan: dict):
        kg = plan.get("kg")
        base = plan["cases"][0]
        endpoint = base.get("endpoint", "")

        covered_endpoints = set()
        for gen in (kg.generations if kg else []):
            for case in gen.get("cases", []):
                if case.get("endpoint"):
                    covered_endpoints.add(case["endpoint"])

        already = endpoint in covered_endpoints
        gaps = []
        if plan["type"] == "api" and not base.get("negative"):
            # A happy-path GET with no negative sibling is a coverage gap.
            gaps.append("negative-case")

        plan["gaps"] = gaps
        plan["coverage"] = {
            "already_covered": already,
            "known_endpoints": len(covered_endpoints),
            "gaps": gaps,
        }
        return self._result(
            f"{'endpoint already covered; ' if already else ''}gaps={gaps or 'none'}"
        )
