---
inclusion: manual
---

# PSI — Playwright Swarm Intelligence (Kiro playbook)

Load this with `#psi` when asked to generate, extend, or repair tests in this
framework. **You are the swarm** — you play all eight agent roles yourself. The
`psi` CLI does only the deterministic work, so this runs entirely inside your
Kiro session with no Bedrock/API key and no per-token cost.

## Token discipline

Never read the whole framework to orient yourself — run `psi context`, which
returns just the relevant slice (~20 tokens vs ~350 for a full dump). If it
reports a `reuse_candidate`, extend that scenario instead of generating a new one.

## Workflow

**1 — Ground (Optimizer + Coverage roles)**
```bash
python -m psi.cli context "<the requirement>"
```
Reuse the returned step texts verbatim; that is what keeps generated tests
runnable with no new step glue.

**2 — Design the plan** wearing each hat:

| Role | Decides |
|------|---------|
| Flow | `api` or `ui`, the journey, feature/scenario name, endpoint + method |
| Coverage | what's already covered; what's missing (usually a negative case) |
| Selector | (UI) stable locators — prefer `role`/`testId` over `css` |
| Assertion | expected status, which response field must be non-empty, or the UI outcome |
| Mutation | extra `cases` for edge conditions (not-found id, invalid payload) |

Write `.psi/plan.json`:
```json
{
  "requirement": "Verify GET /users/7 returns the user email",
  "ticket_id": "JIRA-42",
  "type": "api",
  "feature_name": "User 7 profile",
  "cases": [
    {"name": "User 7 returns an email", "method": "GET", "endpoint": "/users/7",
     "expected_status": 200, "assert_field": "email"},
    {"name": "Unknown user is not found", "method": "GET", "endpoint": "/users/99999999",
     "expected_status": 404, "assert_field": null, "negative": true}
  ]
}
```
`scenario_id` is derived automatically — omit it. For `"type": "ui"` add
`"selectors"` and `"ui_outcome"`.

**3 — Generate (Coder role)**
```bash
python -m psi.cli apply .psi/plan.json
```

**4 — Self-verify gate (definition of done)**
```bash
python -m psi.cli verify "<verify_tag from step 3>"
```

**5 — Self-Healing role (only if red)** — ask reality, don't guess:
```bash
python -m psi.cli probe users/99999999
```
Set that case's `expected_status` to `actual_status`; for 4xx/5xx also set
`assert_field` to `null` and `negative` to `true`. Re-apply (it upserts) and
re-verify. **Max two attempts**, then report the failure class.

**6 — Remember**
```bash
python -m psi.cli record .psi/plan.json
```

## Guardrails

- Never edit committed framework tests to make a generated test pass. Generated
  files are `features/*/gen_*.feature` and `tests/steps/gen_*.py`.
- Never report success on a red verify.
- UI generation produces skeletons that raise `NotImplementedError` until a target
  app is available — say so rather than claiming a passing UI test.

## Report back

Scenario ids, what each case covers, the verify verdict, any healing performed,
and the tokens saved. Summarise — do not paste file contents.
