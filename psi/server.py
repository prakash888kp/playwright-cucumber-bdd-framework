"""PSI MCP server — exposes the Orchestrator as tools over MCP (stdio).

This is the shared entry point both modes build on:
  * Mode 1: Kiro (or any MCP client) launches this server and calls `generate_tests`.
  * Mode 2: the Jira webhook Lambda imports psi.orchestrator directly (no MCP needed).

Run locally:   python -m psi.server
Register in Kiro: see psi/README.md and .kiro/settings/mcp.json
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from psi.orchestrator import Orchestrator  # noqa: E402

mcp = FastMCP("psi-orchestrator")
_orch = Orchestrator()


@mcp.tool()
def generate_tests(requirement: str, ticket_id: str = "", verify: bool = True) -> dict:
    """Generate pytest-bdd + Playwright tests from a plain-language requirement.

    Runs the agent swarm, writes the test files + workbook rows into the
    framework, and (by default) self-verifies by executing the new scenario.
    Returns the scenario id, generated artifacts, agent trace, and verify result.

    Args:
        requirement: What to test, in plain language (e.g. a Jira description).
        ticket_id: Optional source ticket id, used in the scenario id and trace.
        verify: When true, execute the generated scenario before returning.
    """
    return _orch.generate(requirement, ticket_id=ticket_id, verify=verify).to_dict()


@mcp.tool()
def list_agents() -> list[dict]:
    """List the swarm agents and their responsibilities."""
    return _orch.list_agents()


@mcp.tool()
def psi_status() -> dict:
    """Report the active LLM provider (anthropic / bedrock / offline), the model,
    and the agent roster — use this to confirm the swarm is wired to Claude."""
    return _orch.status()


@mcp.tool()
def heal_test(scenario_id: str, failure: str = "") -> dict:
    """Classify a failing scenario and propose a self-healing action."""
    return _orch.heal(scenario_id, failure)


if __name__ == "__main__":
    mcp.run()
