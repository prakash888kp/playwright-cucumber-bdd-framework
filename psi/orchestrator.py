"""Orchestrator — the brain both delivery modes invoke.

Pipeline: Flow -> Coverage -> Selector -> Assertion -> Mutation -> Optimizer ->
Coder, grounded by a scoped Knowledge Graph context (token-optimized). It then
writes the plan, runs the self-verify gate, and on a red result runs the
Self-Healing loop (classify -> fix -> regenerate -> re-verify, bounded). Every
generation is recorded back into the Knowledge Graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

load_env()

from .agents import (  # noqa: E402
    AssertionAgent,
    CoderAgent,
    CoverageAgent,
    FlowAgent,
    HealingAgent,
    MutationAgent,
    OptimizerAgent,
    SelectorAgent,
)
from .knowledge_graph import KnowledgeGraph  # noqa: E402
from .llm import LLM  # noqa: E402
from .models import GenerationResult, Requirement  # noqa: E402
from .verify import run_verify  # noqa: E402
from .writer import apply_data_rows, write_files  # noqa: E402

MAX_HEAL_ATTEMPTS = 2


class Orchestrator:
    def __init__(self) -> None:
        self.llm = LLM()
        self.coder = CoderAgent(self.llm)
        self.pipeline = [
            FlowAgent(self.llm),
            CoverageAgent(self.llm),
            SelectorAgent(self.llm),
            AssertionAgent(self.llm),
            MutationAgent(self.llm),
            OptimizerAgent(self.llm),
            self.coder,
        ]
        self.healer = HealingAgent(self.llm)

    def list_agents(self) -> list[dict]:
        agents = [*self.pipeline, self.healer]
        return [{"agent": a.name, "role": a.role} for a in agents]

    def status(self) -> dict:
        kg = KnowledgeGraph()
        return {
            "llm_provider": self.llm.provider,
            "llm_model": self.llm.model if self.llm.available() else "(offline heuristics)",
            "llm_available": self.llm.available(),
            "agents": self.list_agents(),
            "knowledge_graph": kg.token_report(),
        }

    def generate(self, requirement: str, ticket_id: str = "", verify: bool = True, heal: bool = True) -> GenerationResult:
        req = Requirement(text=requirement, ticket_id=ticket_id)
        kg = KnowledgeGraph()
        ctx = kg.retrieve_context(requirement)
        plan: dict = {"kg": kg, "kg_context": ctx["text"], "kg_context_meta": ctx}

        result = GenerationResult(ticket_id=ticket_id, scenario_id="", feature_name="", verify_tag="")
        for agent in self.pipeline:
            result.trace.append(agent.run(req, plan))

        result.scenario_id = plan["scenario_id"]
        result.feature_name = plan["feature_name"]
        result.verify_tag = plan["verify_tag"]
        result.cases = [c["tc_id"] for c in plan["cases"]]
        result.coverage = plan.get("coverage", {})
        result.optimization = plan.get("optimization", {})

        self._apply(plan, result)

        if verify:
            ok, out = run_verify(result.verify_tag)
            result.verified, result.verify_output = ok, out
            if not ok and heal:
                ok = self._heal_loop(req, plan, result)

        kg.record(requirement, result.scenario_id, plan["cases"], result.optimization.get("tokens_saved_total", 0))
        return result

    # ---------------------------------------------------------------- helpers
    def _apply(self, plan: dict, result: GenerationResult) -> None:
        result.artifacts = plan.get("artifacts", [])
        result.data_rows = plan.get("data_rows", [])
        write_files(result.artifacts)
        apply_data_rows(result.data_rows)

    def _heal_loop(self, req: Requirement, plan: dict, result: GenerationResult) -> bool:
        for attempt in range(1, MAX_HEAL_ATTEMPTS + 1):
            plan["failure"] = result.verify_output
            result.trace.append(self.healer.run(req, plan))   # classify
            if not self.healer.fix(plan):                      # probe reality + correct
                result.heal_summary = f"class={plan.get('failure_class')}; no auto-fix available"
                break
            self.coder.run(req, plan)                          # regenerate from corrected cases
            self._apply(plan, result)
            result.heal_attempts = attempt
            ok, out = run_verify(result.verify_tag)
            result.verified, result.verify_output = ok, out
            if ok:
                result.heal_summary = f"healed on attempt {attempt} (class={plan.get('failure_class')})"
                return True
        if not result.heal_summary:
            result.heal_summary = f"still red after {result.heal_attempts} heal attempt(s)"
        return False

    def heal(self, scenario_id: str, failure: str = "") -> dict:
        plan = {"failure": failure}
        res = self.healer.run(Requirement(text=scenario_id), plan)
        return {"scenario_id": scenario_id, "class": plan.get("failure_class"), "trace": res.summary}
