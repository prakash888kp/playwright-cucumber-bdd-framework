"""BaseAgent — the contract every swarm agent follows.

An agent reads the requirement and the shared `plan` dict, mutates the plan in
place (adds selectors, steps, artifacts, ...), and returns an AgentResult for
the trace. Agents never write to disk — the Orchestrator hands the finished
plan to the writer. This keeps agents pure and testable.
"""
from __future__ import annotations

from ..llm import LLM
from ..models import AgentResult, Requirement


class BaseAgent:
    name: str = "base"
    role: str = "abstract"

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def run(self, req: Requirement, plan: dict) -> AgentResult:
        raise NotImplementedError

    def _result(self, summary: str) -> AgentResult:
        return AgentResult(agent=self.name, role=self.role, summary=summary)
