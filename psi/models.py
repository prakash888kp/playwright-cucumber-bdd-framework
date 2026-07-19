"""Shared data structures passed between the Orchestrator and its agents."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Requirement:
    """A unit of work handed to the swarm — free text plus optional origin."""
    text: str
    ticket_id: str = ""


@dataclass
class GeneratedArtifact:
    """One file the swarm wants written into the framework."""
    path: str      # repo-relative, POSIX style
    content: str
    kind: str      # feature | steps | page | selectors | note


@dataclass
class DataRow:
    """A row to upsert into one of the xlsx workbooks (sheet decides which)."""
    sheet: str     # APIData | LoginData | ... | ExecutionControl
    values: dict


@dataclass
class AgentResult:
    """What an agent reports back to the trace after it runs."""
    agent: str
    role: str
    summary: str


@dataclass
class GenerationResult:
    ticket_id: str
    scenario_id: str
    feature_name: str
    verify_tag: str
    cases: list = field(default_factory=list)          # tc_ids of base + mutations
    artifacts: list = field(default_factory=list)
    data_rows: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)        # covered/gaps from Coverage Agent
    optimization: dict = field(default_factory=dict)    # token savings from Optimizer + KG
    heal_attempts: int = 0
    heal_summary: str = ""
    verified: bool | None = None
    verify_output: str = ""

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "scenario_id": self.scenario_id,
            "feature_name": self.feature_name,
            "verify_tag": self.verify_tag,
            "cases": self.cases,
            "artifacts": [{"path": a.path, "kind": a.kind} for a in self.artifacts],
            "data_rows": [{"sheet": r.sheet, **r.values} for r in self.data_rows],
            "agent_trace": [{"agent": t.agent, "role": t.role, "summary": t.summary} for t in self.trace],
            "coverage": self.coverage,
            "optimization": self.optimization,
            "heal_attempts": self.heal_attempts,
            "heal_summary": self.heal_summary,
            "verified": self.verified,
            "verify_output_tail": self.verify_output[-1200:] if self.verify_output else "",
        }
