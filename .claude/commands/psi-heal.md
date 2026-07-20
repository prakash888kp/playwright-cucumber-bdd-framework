---
description: Diagnose and repair a failing generated test using the PSI self-healing loop (probe reality, correct, re-verify)
---

Heal this failing test: **$ARGUMENTS**

(If no scenario id was given, run `python -m psi.cli status` and ask which one.)

1. Re-run the gate to see the current failure:
   `python -m psi.cli verify "@<scenario_id>"`
2. **Classify** it: selector / assertion / timeout / real regression.
3. **Probe reality instead of guessing** — for an API status mismatch:
   `python -m psi.cli probe <endpoint>`
4. Correct `.psi/plan.json` (for 4xx/5xx set `expected_status` to the probed
   value, `assert_field` to `null`, `negative` to `true`).
5. `python -m psi.cli apply .psi/plan.json` then re-verify.

Stop after two attempts. If it is a genuine product regression, say so clearly
and **do not** weaken the assertion to force it green.
