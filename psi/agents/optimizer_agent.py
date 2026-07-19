"""Optimizer Agent — efficiency + token optimization via the Knowledge Graph.

This is the agent that turns the Knowledge Graph into token savings:

  * Scoped grounding — it uses the KG's `retrieve_context()` slice instead of
    the whole framework, and records how many prompt tokens that saved.
  * Reuse cache — if the KG holds a near-duplicate requirement, it recommends
    reusing that test and skipping the LLM entirely (100% of a generation's
    tokens saved).

The numbers are estimates, surfaced on the result so the saving is visible.
"""
from __future__ import annotations

from ..models import Requirement
from .base import BaseAgent


class OptimizerAgent(BaseAgent):
    name = "optimizer-agent"
    role = "Heuristics + improves efficiency"

    def run(self, req: Requirement, plan: dict):
        kg = plan.get("kg")
        ctx = plan.get("kg_context_meta", {})
        scoped = ctx.get("scoped_tokens", 0)
        full = ctx.get("full_tokens", 0)
        scoped_saving = max(0, full - scoped)

        reuse = kg.find_reusable(req.text) if kg else None
        opt = {
            "scoped_context_tokens": scoped,
            "full_context_tokens": full,
            "tokens_saved_by_scoping": scoped_saving,
            "cache_hit": bool(reuse),
        }
        total_saved = scoped_saving
        if reuse:
            # Reusing an existing test skips the whole LLM generation for this run.
            opt["reuse_of"] = reuse["scenario_id"]
            opt["similarity"] = reuse["score"]
            opt["tokens_saved_by_reuse"] = full
            total_saved += full
        opt["tokens_saved_total"] = total_saved
        plan["optimization"] = opt

        msg = f"scoped saved ~{scoped_saving} tok"
        if reuse:
            msg += f"; cache hit {reuse['scenario_id']} ({reuse['score']}) -> reuse, ~{full} tok saved"
        return self._result(msg)
