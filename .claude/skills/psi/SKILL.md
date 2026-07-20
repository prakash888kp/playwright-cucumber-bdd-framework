---
name: psi
description: Playwright Swarm Intelligence — turn a plain-language requirement or Jira ticket into pytest-bdd + Playwright tests in this framework, then self-verify and self-heal them. Use when asked to "generate tests for X", "write a test for this ticket", "add coverage for Y", "fix this failing generated test", or when the user mentions PSI / the swarm / the test agents.
---

# PSI — Playwright Swarm Intelligence (IDE-native)

**You are the swarm.** You play all eight agent roles yourself, in one pass. The
`psi` CLI does only the deterministic work (knowledge retrieval, writing files,
running tests, probing endpoints) — it never calls an LLM, so this costs nothing
beyond the IDE session you are already in.

## Token discipline (important)

- **Never read the whole framework** to "understand it". Run `psi context` — it
  returns only the slice relevant to this requirement (typically ~20 tokens vs
  ~350 for a full dump).
- If `psi context` reports a `reuse_candidate`, **prefer extending that scenario**
  over generating a new one, and say so.
- Do not re-read files you already have in context. Do not paste generated file
  contents back to the user — summarise them.

## The workflow

### 1. Ground yourself (Optimizer + Coverage roles)

```bash
python -m psi.cli context "<the requirement>"
```

Read `scoped_context` (reusable steps, selectors, pages), the `tokens` savings,
and `reuse_candidate`. Reuse the listed step texts **verbatim** — that is what
keeps generated tests consistent and runnable with no new step glue.

### 2. Design the plan (Flow → Coverage → Selector → Assertion → Mutation roles)

Think through the requirement wearing each hat, then write a plan JSON:

| Role | What you decide |
|------|-----------------|
| **Flow Agent** | Is this `api` or `ui`? The journey, the feature/scenario name, the endpoint + method. |
| **Coverage Agent** | Does the KG already cover this endpoint? What's missing — usually a negative case. |
| **Selector Agent** | (UI only) stable locators as descriptor dicts — prefer `role`/`testId` over `css`. |
| **Assertion Agent** | What "correct" means: expected status, which response field must be non-empty, or the visible UI outcome. |
| **Mutation Agent** | Add edge cases as extra entries in `cases` — e.g. a not-found id, an invalid payload. |

Plan schema (write it to a file, e.g. `.psi/plan.json`):

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

Notes: `scenario_id` is derived automatically (stable per requirement+ticket) —
omit it. For `type: "ui"` add `"selectors": {"NAME": {"role": "button", "name": "Login"}}`
and `"ui_outcome": "..."`.

### 3. Generate (Coder role)

```bash
python -m psi.cli apply .psi/plan.json
```

This renders the feature file (one Gherkin scenario per case, reusing the
framework's generic data-driven steps), upserts the `testdata.xlsx` +
`execution-control.xlsx` rows, and prints the `verify_tag`.

### 4. Self-verify gate — nothing is done until it runs green

```bash
python -m psi.cli verify "<verify_tag from step 3>"
```

### 5. Self-Healing role (only if step 4 is FAILED)

Classify the failure, then fix it:

- **Status mismatch** (most common) — ask reality, don't guess:
  ```bash
  python -m psi.cli probe users/99999999
  ```
  Set that case's `expected_status` to `actual_status`. If it's 4xx/5xx also set
  `"assert_field": null` and `"negative": true`.
- **Wrong field** — pick a field that exists in the response.
- **Selector/UI failure** — the generated UI skeletons raise `NotImplementedError`
  by design; complete the page object and steps, or tell the user the target app
  is needed.

Then **re-apply and re-verify** (`apply` upserts, so corrections overwrite):

```bash
python -m psi.cli apply .psi/plan.json && python -m psi.cli verify "<verify_tag>"
```

Stop after **two** heal attempts. If it is still red, report the failure class
and what you tried — do not keep looping.

### 6. Remember it (Knowledge Graph)

```bash
python -m psi.cli record .psi/plan.json
```

This makes the next similar requirement a cache hit instead of a regeneration.

## Report back

Tell the user, briefly: the scenario id(s), what each case covers, the verify
verdict, whether healing was needed (and what it corrected), and the tokens saved
per `psi context`. Do not paste whole files.

## Guardrails

- **Never edit committed framework tests** (`features/ui/login.feature`,
  `features/api/users.feature`, existing steps/pages) to make a generated test
  pass. Generated files are `features/*/gen_*.feature` and `tests/steps/gen_*.py`.
- **Never mark work done on a red verify.** The gate is the definition of done.
- If the user has no target web app running, UI generation produces skeletons —
  say so rather than claiming a passing UI test.

## Other commands

```bash
python -m psi.cli status     # Knowledge-Graph token report + framework index
```
