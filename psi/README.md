# PSI — Playwright Swarm Intelligence (Orchestrator + MCP server)

The shared agentic core that turns a plain-language requirement into pytest-bdd +
Playwright tests **in this framework**, then self-verifies them before they are
offered as a PR. Both delivery modes call the same Orchestrator:

- **Mode 1 — AI-assisted (local):** Kiro CLI/chat launches the MCP server
  (`psi.server`) and calls the `generate_tests` tool. Human in the loop.
- **Mode 2 — autonomous (AWS):** a Jira webhook Lambda imports
  `psi.orchestrator.Orchestrator` directly and opens a PR with the branch link
  posted back to the ticket.

## Pipeline (8 agents)

```
requirement + scoped Knowledge-Graph context
   -> Flow Agent       (journey, test type, scenario id, base case)
   -> Coverage Agent   (graph-diff vs KG; finds gaps e.g. missing negative case)
   -> Selector Agent   (stable locators — UI only)
   -> Assertion Agent  (validation logic)
   -> Mutation Agent   (edge cases — e.g. a not-found negative case)
   -> Optimizer Agent  (KG token optimization: scope context / reuse cache)
   -> Coder Agent      (renders feature/steps/page/selectors + workbook rows)
   -> writer           (upsert files + xlsx rows)
   -> self-verify      (scripts/run.py --tags <ids>)  --green--> ready for PR
                                                       --red----> Self-Healing loop
                                                                   (classify -> probe
                                                                    reality -> fix ->
                                                                    regenerate -> re-verify)
   -> record into the Knowledge Graph
```

API scenarios reuse the framework's existing generic, data-driven steps, so a
generated API test — base **and** the Mutation Agent's negative case — **runs and
passes for real** with no new step glue. UI scenarios get a page object +
selectors + step skeletons to complete.

## Knowledge Graph — grounding + token optimization

`psi/knowledge_graph.py` is the swarm's memory (`.psi/knowledge-graph.json`,
offline, no database). It does two jobs:

1. **Grounding** — it indexes the whole framework (reusable steps, selectors,
   page objects, features) plus every test the swarm has generated, so new code
   stays consistent with what exists.
2. **Token optimization** — instead of dumping the entire framework into every
   prompt, `retrieve_context()` returns only the slice relevant to the
   requirement (measured: ~10 tokens vs ~340 for the full framework in the demo,
   ~97% saved). `find_reusable()` detects a near-duplicate of a past requirement
   so the swarm reuses an existing test and skips the LLM entirely. Savings are
   accumulated and shown via the `psi_status` tool.

The Optimizer Agent surfaces per-generation token savings on the result
(`optimization.tokens_saved_total`, `cache_hit`, `reuse_of`).

## LLM providers — Claude API, Bedrock, or offline

The agents reason through a pluggable provider (`psi/llm.py`), auto-detected or
forced with `PSI_LLM_PROVIDER`:

| Provider | Selected when | Model (default) |
|----------|---------------|-----------------|
| `anthropic` | `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` set, or an `ant auth login` profile | `claude-opus-4-8` (`PSI_ANTHROPIC_MODEL`) |
| `bedrock` | AWS credentials present | `anthropic.claude-3-5-sonnet-...` (`PSI_BEDROCK_MODEL_ID`) |
| `offline` | neither | deterministic heuristics |

Auto-detection order: Anthropic → Bedrock → offline. Everything runs offline
with no cloud access; add a Claude API key or AWS creds to switch on real
reasoning. Call the `psi_status` tool to confirm which provider is active.

## Run it

```bash
pip install -r requirements.txt          # framework deps
pip install -r psi/requirements.txt      # + MCP SDK, anthropic SDK

# Direct (no MCP, offline heuristic — works with no cloud access):
python -c "from psi.orchestrator import Orchestrator; import json; \
print(json.dumps(Orchestrator().generate('Verify the API returns user 2', ticket_id='DEMO-1').to_dict(), indent=2))"

# With the Claude API (Anthropic SDK resolves ANTHROPIC_API_KEY or `ant auth`):
PSI_LLM_PROVIDER=anthropic python -m psi.server

# As an MCP server (offline/auto):
python -m psi.server
```

## Wire into an MCP client (Kiro, Claude Code, Claude Desktop)

The server speaks standard MCP over stdio, so any MCP host can drive it:

- **Kiro** — `.kiro/settings/mcp.json` (included).
- **Claude Code** — `.mcp.json` at the repo root (included); or `claude mcp add psi-orchestrator -- python -m psi.server` from the project directory.
- **Claude Desktop** — add to `claude_desktop_config.json`:

  ```json
  {
    "mcpServers": {
      "psi-orchestrator": {
        "command": "python",
        "args": ["-m", "psi.server"],
        "cwd": "/absolute/path/to/playwright-test",
        "env": { "PSI_LLM_PROVIDER": "anthropic" }
      }
    }
  }
  ```

Then, in the client's chat:

> generate tests for: "As a user I want GET /users/3 to return my profile" (ticket DEMO-3)

The host calls `generate_tests`, the swarm writes the files, and the self-verify
result comes back inline. `psi_status` reports the active provider/model.

## Calling reference — every entry point

### A) MCP tools (from Kiro / Claude Code / Claude Desktop)

The server exposes four tools. In chat you usually just describe the task and the
host picks the tool, but here are the exact signatures:

| Tool | Signature | Purpose |
|------|-----------|---------|
| `generate_tests` | `(requirement: str, ticket_id: str = "", verify: bool = True) -> dict` | Run the full swarm: generate → write → self-verify (→ self-heal on red). Returns the scenario id, cases, coverage, token-optimization stats, heal result, and verify verdict. |
| `psi_status` | `() -> dict` | Active LLM provider + model, the 8-agent roster, and the Knowledge-Graph token report. Use this first to confirm the setup. |
| `list_agents` | `() -> list` | The agent roster and each agent's responsibility. |
| `heal_test` | `(scenario_id: str, failure: str = "") -> dict` | Classify a failure and suggest a healing action (ad-hoc; the generate flow already heals automatically). |

Example chat prompts:

> **psi_status** — "check the PSI status"
> **generate_tests** — `generate tests for: "Verify GET /users/4 returns the user's email" (ticket JIRA-42)`

### B) Python API (scripts, Mode 2 webhook handler, embedding)

```python
from psi.orchestrator import Orchestrator

orch = Orchestrator()                 # picks the LLM provider from the environment

# Full generate → write → self-verify → self-heal:
result = orch.generate(
    "Verify GET /users/4 returns the user's email",
    ticket_id="JIRA-42",
    verify=True,   # run the generated scenario through scripts/run.py
    heal=True,     # on a red verify, classify → probe reality → fix → re-verify
)
print(result.to_dict())

orch.status()                          # provider/model + agents + KG token report
orch.list_agents()                     # roster
orch.heal("TC_GEN_ABC123", failure="...")   # ad-hoc classify + advise
```

`result.to_dict()` keys:

| Key | Meaning |
|-----|---------|
| `scenario_id` | Base scenario id (e.g. `TC_GEN_8178A5`) |
| `verify_tag` | Tag expression used to run all cases (`@TC_… or @TC_…_M1`) |
| `cases` | Every scenario id generated — base **and** the Mutation Agent's edge cases |
| `coverage` | `{already_covered, known_endpoints, gaps}` from the Coverage Agent |
| `optimization` | `{scoped_context_tokens, full_context_tokens, tokens_saved_total, cache_hit, reuse_of?, similarity?}` |
| `heal_attempts` / `heal_summary` | Self-healing outcome |
| `verified` | Did the generated test(s) pass the self-verify gate |
| `artifacts` / `data_rows` | Files written + workbook rows upserted |
| `agent_trace` | One line per agent that ran, in order |

### C) The agents

Agents are **not called individually** — the Orchestrator threads a shared plan
through them in order (see the pipeline above). To add a ninth agent: subclass
`agents/base.py` `BaseAgent`, implement `run(req, plan)` (mutate `plan`, return
`self._result(...)`), and insert it into `Orchestrator.pipeline`.

### D) Environment knobs

| Var | Default | Effect |
|-----|---------|--------|
| `PSI_LLM_PROVIDER` | auto | `anthropic` \| `bedrock` \| `offline` |
| `PSI_ANTHROPIC_MODEL` | `claude-opus-4-8` | Claude API model |
| `PSI_BEDROCK_MODEL_ID` | `anthropic.claude-3-5-sonnet-...` | Bedrock model |
| `API_BASE_URL` | from `.env` | Endpoint base the Self-Healing Agent probes |

## Files

| File | Role |
|------|------|
| `server.py` | MCP server exposing `generate_tests`, `list_agents`, `heal_test` |
| `orchestrator.py` | The brain — pipeline, writer, verify gate, self-healing loop, KG |
| `agents/` | Flow, Coverage, Selector, Assertion, Mutation, Optimizer, Coder, Self-Healing |
| `knowledge_graph.py` | Framework + generation memory; scoped-context retrieval + reuse cache |
| `llm.py` | Claude API / Bedrock / offline provider |
| `writer.py` | Upserts files + workbook rows (heal-safe) |
| `verify.py` | Self-verify gate via the real run funnel |

## Roadmap (Phase 2 / Mode 2)

- Mode 2: Jira webhook -> SQS -> Orchestrator -> open PR + comment branch on the ticket
- Graduate the Knowledge Graph store to Neptune + OpenSearch (embeddings) at scale
- Prove the live Claude/Bedrock reasoning path against a real model + target app
- AWS deployment (Step Functions, CodeBuild, Bedrock) per the Figma board
