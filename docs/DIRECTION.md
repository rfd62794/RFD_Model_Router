# Direction: RFD_Model_Router

## Purpose

Task-type LLM router: a YAML map (`routing_config.yaml`) routes `task_type` to a
provider+model, dispatched through thin SDK adapters, exposed on two network front
doors — REST `POST /route` on `0.0.0.0:8005` and an MCP SSE server with one tool
`route_completion` on `0.0.0.0:8004` — with a SQLite request log
(`docs/AUDIT.md` §1; `pyproject.toml` scripts; `docs/retirement/RFD_Model_Router.md` §1).

## Current state

- **Retirement planned.** Robert marked the repo `RETIREMENT PLANNED` on 2026-09-23
  (Portfolio `projects.yaml`, recorded in `docs/retirement/RFD_Model_Router.md`
  header). The retirement review verdict: **archive-ready, conditional on one
  host-side check** that nothing calls `:8004`/`:8005` (same doc, Verdict + §5).
- The code is much smaller than its charter implied: no fallback chain, no
  pricing, no throttling, no spend cap, no auth, no health/quarantine, and no
  RunPod adapter — a single-provider-per-task-type dispatcher plus a log
  (`docs/AUDIT.md`, headline + §2-3).
- Tests: `uv run pytest -q` → **25 passed, 0 failed** (`docs/AUDIT.md` test
  count; `docs/retirement/RFD_Model_Router.md` test state). Provider calls are
  mocked; no live calls.
- Last real code commit: `f11ab07`, 2026-06-19 — ~3 months stale; everything
  since is directive-queue bookkeeping plus `docs/AUDIT.md`
  (`docs/retirement/RFD_Model_Router.md`, "Last real commit").
- No README, no `AGENTS.md`/`CLAUDE.md`; documentation is `docs/AUDIT.md`,
  `docs/retirement/`, and `docs/directives/` (`docs/retirement/RFD_Model_Router.md` §1).

## Next steps

The repo's own stated path is a clean wind-down, in this order
(`docs/retirement/RFD_Model_Router.md`):

1. **Close the caller question** — host-side check that nothing connects to
   `:8004`/`:8005` (connection log, MCP client config, scheduled tasks / lane
   configs). This is the single gate on archive (§5).
2. **Salvage to AgentFlow `packages/models`** — `routing_config.yaml`, the
   `router.py`/`BaseAdapter` dispatch shape, and the anthropic/groq/openrouter
   adapters (~100 lines + the 19-line map). Gemini adapter, REST/MCP shells,
   SQLite logger, and tests are marked drop (§3-4).
3. **Work the deregistration list** — MCP client config entry, listener
   launchers, scheduled tasks/lane configs that call it, env-var check,
   `requests.db` disposition (§2.3).
4. **Robert archives the repo** — the final step is his alone (§2.3 item 6).

## Definition of done

This repo is done when: the host-side caller check is recorded and clean, the
salvage has landed in AgentFlow `packages/models`, the §2.3 deregistration list
is worked, and Robert has archived the repository. Until then the suite stays
green (`uv run pytest -q`) and no new capability is added.

## Do not

- Do not build the missing capabilities here (auth, fallback, pricing, health/
  quarantine) — that work belongs to AgentFlow `packages/models`; this repo is
  being retired, not grown (`docs/AUDIT.md` §4, `docs/retirement/` §4).
- Do not archive, deregister, stop the service, or edit host configs from a
  directive run — report only, Robert acts (`docs/directives/Retire_Model_Router_Directive.md` §4).
- Do not make live provider or network calls; the suite mocks them
  (`docs/directives/Model_Router_Audit_Directive.md` §3; `docs/AUDIT.md` method note).
- Do not port `adapters/gemini_adapter.py`, `api.py`, `server.py`, `logger.py`,
  or `tests/` — the salvage list marks them drop (`docs/retirement/RFD_Model_Router.md` §3).

## Sources of truth

- `docs/AUDIT.md` — capability matrix, gaps/risks, the three options (2026-09-23).
- `docs/retirement/RFD_Model_Router.md` — verdict, who-calls-this, salvage list,
  deregistration list (2026-09-23).
- `routing_config.yaml` — the live task_type→provider+model map.
- `pyproject.toml` — entry points and dependencies.
- `docs/directives/` — queue history; Portfolio `projects.yaml` (outside this
  repo) holds the `RETIREMENT PLANNED` marker per the retirement doc.
