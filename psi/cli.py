"""PSI CLI — the deterministic toolbelt for IDE-native agents (zero API cost).

When the swarm runs *inside* an IDE (Kiro, Claude Code), the IDE's own model does
all the reasoning — it plays the eight agent roles — so no Bedrock/Anthropic API
key and no per-token cost. This CLI gives that model the deterministic muscle it
cannot do by "thinking":

  psi context "<requirement>"   -> scoped Knowledge-Graph context (token-optimized)
                                   + reuse-cache hit if a near-duplicate exists
  psi apply  <plan.json>        -> render the plan into framework files + xlsx rows
  psi verify "<tag expr>"       -> run the generated scenarios (self-verify gate)
  psi probe  <endpoint>         -> real HTTP status, for the self-healing loop
  psi record <plan.json>        -> remember this generation in the Knowledge Graph
  psi status                    -> KG token report + framework index

Everything here is pure Python — it never calls an LLM.

Usage:  python -m psi.cli <command> [...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

load_env()

from psi.agents.coder_agent import CoderAgent  # noqa: E402
from psi.agents.healing_agent import HealingAgent  # noqa: E402
from psi.knowledge_graph import KnowledgeGraph  # noqa: E402
from psi.llm import LLM  # noqa: E402
from psi.models import Requirement  # noqa: E402
from psi.verify import run_verify  # noqa: E402
from psi.writer import apply_data_rows, write_files  # noqa: E402


def _out(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _load_plan(path: str) -> dict:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def _scenario_id(plan: dict) -> str:
    if plan.get("scenario_id"):
        return plan["scenario_id"]
    seed = f"{plan.get('ticket_id', '')}|{plan.get('requirement', '')}".encode()
    return "TC_GEN_" + hashlib.sha1(seed).hexdigest()[:6].upper()


def _normalise(plan: dict) -> dict:
    """Fill the defaults the Coder Agent expects, so the IDE model only has to
    supply the interesting fields."""
    plan.setdefault("type", "api")
    plan["scenario_id"] = _scenario_id(plan)
    plan.setdefault("feature_name", plan.get("requirement", "Generated test")[:60])
    plan.setdefault("scenario_name", f"Verify {plan['feature_name']}")
    plan.setdefault("selectors", {})
    plan.setdefault("ui_outcome", "the expected result is visible")

    cases = plan.get("cases") or []
    if not cases:
        cases = [{}]
    for i, case in enumerate(cases):
        case.setdefault("tc_id", plan["scenario_id"] if i == 0 else f"{plan['scenario_id']}_M{i}")
        case.setdefault("name", plan["scenario_name"] if i == 0 else f"{plan['scenario_name']} - case {i}")
        case.setdefault("method", "GET")
        case.setdefault("endpoint", "/users/1")
        case.setdefault("expected_status", 200)
        case.setdefault("assert_field", None if case.get("negative") else "name")
        case.setdefault("negative", False)
    plan["cases"] = cases
    return plan


# ---------------------------------------------------------------- commands

def cmd_context(args) -> int:
    """Token-optimized grounding: only the framework slice this requirement needs."""
    kg = KnowledgeGraph()
    ctx = kg.retrieve_context(args.requirement)
    reuse = kg.find_reusable(args.requirement)
    _out(
        {
            "scoped_context": ctx["text"],
            "tokens": {
                "scoped": ctx["scoped_tokens"],
                "full_framework": ctx["full_tokens"],
                "saved_by_scoping": ctx["tokens_saved"],
            },
            "reuse_candidate": reuse,
            "hint": (
                "Reuse the listed steps/selectors verbatim so generated code stays consistent. "
                "If reuse_candidate is not null, prefer extending that scenario over writing a new one."
            ),
        }
    )
    return 0


def cmd_apply(args) -> int:
    """Render a plan into real framework files + workbook rows (no LLM)."""
    plan = _normalise(_load_plan(args.plan))
    CoderAgent(LLM()).run(Requirement(text=plan.get("requirement", ""), ticket_id=plan.get("ticket_id", "")), plan)
    written = write_files(plan["artifacts"])
    rows = apply_data_rows(plan["data_rows"])
    _out(
        {
            "scenario_id": plan["scenario_id"],
            "verify_tag": plan["verify_tag"],
            "files_written": written,
            "data_rows": rows,
            "next": f'python -m psi.cli verify "{plan["verify_tag"]}"',
        }
    )
    return 0


def cmd_verify(args) -> int:
    """The self-verify gate — nothing is done until the generated test runs green."""
    ok, out = run_verify(args.tags)
    _out({"verified": ok, "verdict": "PASSED" if ok else "FAILED", "output_tail": out[-1500:]})
    return 0 if ok else 1


def _norm_endpoint(ep: str) -> str:
    """Accept `/users/1`, `users/1`, or the mangled form Git Bash on Windows
    produces when it rewrites a leading slash into `C:/Program Files/Git/...`."""
    ep = ep.replace("\\", "/")
    if "/Git/" in ep:
        ep = "/" + ep.split("/Git/", 1)[1]
    if not ep.startswith(("/", "http")):
        ep = "/" + ep
    return ep


def cmd_probe(args) -> int:
    """Self-healing helper: what status does this endpoint ACTUALLY return?"""
    endpoint = _norm_endpoint(args.endpoint)
    status = HealingAgent(LLM()).probe(endpoint)
    _out(
        {
            "endpoint": endpoint,
            "actual_status": status,
            "hint": "If this differs from the plan, set expected_status to it; for 4xx/5xx also set "
                    "assert_field to null and negative to true, then re-apply and re-verify.",
        }
    )
    return 0


def cmd_record(args) -> int:
    """Remember this generation so future runs reuse it instead of regenerating."""
    plan = _normalise(_load_plan(args.plan))
    kg = KnowledgeGraph()
    ctx = kg.retrieve_context(plan.get("requirement", ""))
    kg.record(plan.get("requirement", ""), plan["scenario_id"], plan["cases"], ctx["tokens_saved"])
    _out({"recorded": plan["scenario_id"], "knowledge_graph": kg.token_report()})
    return 0


def cmd_status(args) -> int:
    kg = KnowledgeGraph()
    _out(
        {
            "knowledge_graph": kg.token_report(),
            "framework_index": {k: len(v) for k, v in kg.framework.items()},
            "mode": "IDE-native (the IDE model reasons; this CLI does the deterministic work)",
        }
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psi", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("context", help="scoped Knowledge-Graph context for a requirement")
    p.add_argument("requirement")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("apply", help="render a plan JSON into framework files + xlsx rows")
    p.add_argument("plan", help="path to plan.json, or - for stdin")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("verify", help="run the generated scenarios through the real run funnel")
    p.add_argument("tags", help='tag expression, e.g. "@TC_GEN_ABC123 or @TC_GEN_ABC123_M1"')
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("probe", help="actual HTTP status for an endpoint (self-healing)")
    p.add_argument("endpoint")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("record", help="record the generation in the Knowledge Graph")
    p.add_argument("plan", help="path to plan.json, or - for stdin")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("status", help="Knowledge Graph token report + framework index")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
