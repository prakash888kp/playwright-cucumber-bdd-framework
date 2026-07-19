"""PSI — Playwright Swarm Intelligence.

The shared agentic core that both delivery modes invoke:
  * Mode 1 (AI-assisted, local): Kiro CLI/chat -> MCP server (psi.server) -> Orchestrator
  * Mode 2 (autonomous, AWS): Jira comment -> webhook -> Orchestrator

The Orchestrator drives a swarm of agents (Flow, Selector, Assertion, Coder, ...)
that turn a plain-language requirement into pytest-bdd + Playwright test code in
this framework, then runs a self-verify gate before the code is offered as a PR.
"""
