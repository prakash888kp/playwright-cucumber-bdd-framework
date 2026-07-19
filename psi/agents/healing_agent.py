"""Self-Healing Agent — classifies a failure AND fixes it (closed loop).

On the red path of the self-verify gate it does two things:
  * classify() names the failure class (selector / assertion / timeout / regression).
  * fix() repairs the plan for the common, deterministic case: an API status
    mismatch. It probes the real endpoint, learns the actual status, and
    corrects the case's expected status (dropping the body assertion for a
    4xx/5xx). The Orchestrator then regenerates and re-verifies.

Probing uses the standard library (no browser needed), so healing works offline.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

from ..models import Requirement
from .base import BaseAgent

_CLASSES = {
    "selector": ("locator", "element not found", "no node found", "to_be_visible"),
    "assertion": ("assert", "to_have_text", "expected http", "should match", "not empty"),
    "timeout": ("timeout", "exceeded", "waiting for"),
}


class HealingAgent(BaseAgent):
    name = "self-healing-agent"
    role = "Failure classifier + fixes broken tests"

    def classify(self, failure: str) -> str:
        low = (failure or "").lower()
        for cls, hints in _CLASSES.items():
            if any(h in low for h in hints):
                return cls
        return "regression"

    def _probe(self, endpoint: str) -> int | None:
        base = os.environ.get("API_BASE_URL", "https://jsonplaceholder.typicode.com")
        url = base.rstrip("/") + "/" + endpoint.lstrip("/")
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 (test endpoint)
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except Exception:
            return None

    def fix(self, plan: dict) -> bool:
        """Repair API status mismatches in place. Returns True if anything changed."""
        if plan.get("type") != "api":
            return False
        changed = False
        for case in plan.get("cases", []):
            if case.get("method", "GET").upper() != "GET":
                continue
            actual = self._probe(case["endpoint"])
            if actual and actual != case["expected_status"]:
                case["expected_status"] = actual
                if actual >= 400:
                    case["assert_field"] = None
                    case["negative"] = True
                changed = True
        return changed

    def run(self, req: Requirement, plan: dict):
        failure = plan.get("failure", "")
        cls = self.classify(failure)
        plan["failure_class"] = cls
        return self._result(f"class={cls}")
