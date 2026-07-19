"""Coder Agent — turns the plan (all cases) into real framework files.

API scenarios are rendered against the framework's existing generic, data-driven
steps (no new step glue needed), so generated API tests run and self-verify for
real — including the Mutation Agent's negative cases. Each case becomes one
Gherkin scenario plus one APIData row and one control-sheet row. UI scenarios
also get a page object, a selectors file, and step skeletons to complete.

Coder is idempotent per generation: it rebuilds the plan's artifacts/data_rows
from scratch each time it runs, so the Orchestrator can re-run it after the
Self-Healing Agent edits the cases.
"""
from __future__ import annotations

import re

from ..models import DataRow, GeneratedArtifact, Requirement
from .base import BaseAgent


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "generated"


class CoderAgent(BaseAgent):
    name = "coder-agent"
    role = "Generates Playwright code"

    def run(self, req: Requirement, plan: dict):
        plan["artifacts"] = []
        plan["data_rows"] = []
        if plan["type"] == "api":
            self._render_api(plan)
        else:
            self._render_ui(plan)
        plan["verify_tag"] = " or ".join(f"@{c['tc_id']}" for c in plan["cases"])
        return self._result(
            f"{len(plan['artifacts'])} file(s), {len(plan['cases'])} scenario(s), "
            f"{len(plan['data_rows'])} data row(s)"
        )

    # -- API: reuse existing generic steps -> genuinely runnable ------------
    def _render_api(self, plan: dict) -> None:
        base_tc = plan["scenario_id"]
        scenarios = []
        for case in plan["cases"]:
            steps = [
                f'    Given I load API data for "{case["tc_id"]}"',
                "    When I send a GET request to the endpoint from test data",
                "    Then the response status should match the expected status",
            ]
            if case.get("assert_field"):
                steps.append(f'    And the response field "{case["assert_field"]}" should not be empty')
            scenarios.append(
                f"  @{case['tc_id']} @regression\n"
                f"  Scenario: {case['name']}\n" + "\n".join(steps) + "\n"
            )
            plan["data_rows"].append(
                DataRow(
                    "APIData",
                    {
                        "TC_ID": case["tc_id"],
                        "Method": case["method"],
                        "Endpoint": case["endpoint"],
                        "Payload": "",
                        "ExpectedStatus": case["expected_status"],
                    },
                )
            )
            plan["data_rows"].append(
                DataRow(
                    "ExecutionControl",
                    {
                        "Feature": f"Generated - {plan['feature_name']}",
                        "ScenarioID": case["tc_id"],
                        "ScenarioName": case["name"],
                        "Type": "API",
                        "Run": "YES",
                    },
                )
            )
        feature = (
            f"@api @generated\nFeature: Generated - {plan['feature_name']}\n\n"
            + "\n".join(scenarios)
        )
        plan["artifacts"].append(
            GeneratedArtifact(f"features/api/gen_{base_tc}.feature", feature, "feature")
        )

    # -- UI: page + selectors + feature + step skeletons -------------------
    def _render_ui(self, plan: dict) -> None:
        tc = plan["scenario_id"]
        name = _slug(plan["feature_name"])
        cls = "".join(p.capitalize() for p in name.split("_")) + "Page"
        selectors = plan.get("selectors", {})

        sel_body = "\n".join(f"{k} = {v!r}" for k, v in selectors.items()) or "# TODO: add selectors"
        plan["artifacts"].append(
            GeneratedArtifact(
                f"framework/selectors/{name}_selectors.py",
                f'"""Selectors for {plan["feature_name"]} (generated)."""\n{sel_body}\n',
                "selectors",
            )
        )
        page = (
            f"from ..selectors import {name}_selectors as SEL  # noqa: F401\n"
            f"from .base_page import BasePage\n\n\n"
            f"class {cls}(BasePage):\n"
            f'    """Generated page object — flows to be completed by the swarm/human."""\n\n'
            f"    def open_page(self):\n        self.open('/')\n\n"
            f"    def perform(self):\n"
            f"        # TODO: drive the journey for: {plan['feature_name']}\n"
            f"        raise NotImplementedError\n"
        )
        plan["artifacts"].append(GeneratedArtifact(f"framework/pages/{name}_page.py", page, "page"))

        feature = (
            f"@ui @generated\nFeature: Generated - {plan['feature_name']}\n\n"
            f"  @{tc} @regression\n  Scenario: {plan['scenario_name']}\n"
            f"    Given the {name} page is open\n"
            f"    When the {name} journey is performed\n"
            f"    Then {plan.get('ui_outcome', 'the expected result is visible')}\n"
        )
        plan["artifacts"].append(GeneratedArtifact(f"features/ui/gen_{tc}.feature", feature, "feature"))

        steps = (
            f'"""Generated steps for {plan["feature_name"]}."""\n'
            f"from pytest_bdd import parsers, step  # noqa: F401\n\n\n"
            f'@step("the {name} page is open")\n'
            f"def _open(context):\n    raise NotImplementedError\n\n\n"
            f'@step("the {name} journey is performed")\n'
            f"def _perform(context):\n    raise NotImplementedError\n\n\n"
            f"@step(parsers.re(r'.*expected result is visible'))\n"
            f"def _assert(context):\n    raise NotImplementedError\n"
        )
        plan["artifacts"].append(GeneratedArtifact(f"tests/steps/gen_{tc}_steps.py", steps, "steps"))
