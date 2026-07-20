---
description: Generate pytest-bdd + Playwright tests from a requirement, then self-verify and self-heal them (PSI swarm, runs in-IDE — no API cost)
---

Run the PSI swarm for this requirement:

**$ARGUMENTS**

Follow the `psi` skill workflow exactly:

1. `python -m psi.cli context "<requirement>"` — ground yourself on the scoped
   Knowledge-Graph slice; honour any `reuse_candidate`.
2. Design the plan wearing the Flow / Coverage / Selector / Assertion / Mutation
   hats — include at least one edge case.
3. `python -m psi.cli apply .psi/plan.json`
4. `python -m psi.cli verify "<verify_tag>"` — the gate.
5. If red: classify, `python -m psi.cli probe <endpoint>`, correct the plan,
   re-apply, re-verify. Max two attempts.
6. `python -m psi.cli record .psi/plan.json`

Report the scenario ids, what each case covers, the verify verdict, any healing
performed, and the tokens saved. Do not paste file contents.
