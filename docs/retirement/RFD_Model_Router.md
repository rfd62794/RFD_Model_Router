# RFD_Model_Router — Retirement Review

Date: 2026-09-23 · Branch: `directive/rfd-model-router-retire-model-router-directive` · Base commit: `6550b4d`
Context: Robert marked the repo `RETIREMENT PLANNED` on 2026-09-23 (Portfolio `projects.yaml`, agentstack MCP sweep). This report audits and lists salvage only — it archives, deregisters, and deletes nothing. It builds on `docs/AUDIT.md` (2026-09-23); every claim there was re-verified against the live tree in this run.

## Verdict

**archive-ready, conditional on one host-side check.** Nothing inside the repo names a live caller; the only open risk is a runtime caller over HTTP/MCP (§2). Once a host-side check confirms nothing connects to `:8004`/`:8005` and the deregistration list in §2.3 is worked, Robert can archive.

## 1. Audit

### Entry points / README

- **No README**, no `AGENTS.md`/`CLAUDE.md`. Documentation is `docs/AUDIT.md` plus `docs/directives/`.
- Console scripts (`pyproject.toml:17-19`): `rfd-model-router` → `server:main` (MCP SSE on `0.0.0.0:8004`, `sse_path=/mcp`, `message_path=/messages/`); `rfd-model-router-api` → `api:main` (uvicorn on `0.0.0.0:8005`).
- Package `rfd_model_router` — 5 modules + 4 adapters, ~180 lines of real logic; Python ≥3.12, uv workspace.

### What the router serves

- **REST:** `POST /route` — `{task_type, messages, system_prompt?}` → `{completion, provider, model, tokens{input,output}}` (`api.py:28-56`). **Custom schema, not OpenAI-compatible** — there is no `/v1/chat/completions` surface. (Correction to the directive's "OpenAI-compatible API" description: the OpenAI SDK is used only *outbound*, inside the OpenRouter adapter.)
- **MCP:** `FastMCP("rfd-model-router")`, one tool `route_completion(task_type, messages, system_prompt?) -> str` — returns completion text only (`server.py:8-36`).
- **Model map** (`routing_config.yaml`, 19 lines): `code_transformation` → groq/llama-3.1-70b-versatile; `code_construction` → anthropic/claude-haiku-4-5-20251001; `content` → gemini/gemini-2.0-flash-exp; `directive` → anthropic/claude-sonnet-4-6; `default` → anthropic/claude-haiku-4-5-20251001. Unknown task_type warns and falls back to `default` (`router.py:43-46`).
- **Logging:** SQLite `requests.db` in repo root (gitignored) — `task_type, provider, model, input_tokens, output_tokens, duration_ms, success` (`logger.py:11-24`). On failure, provider/model are written as `"unknown"`.
- **Absent:** no auth on either listener (both bind `0.0.0.0`), no fallback chain, no pricing, no spend cap, no throttle, no health/quarantine — the charter description overstates the code (full matrix in `docs/AUDIT.md` §2-3).

### Test state

- `uv run pytest -q`: **25 passed, 0 failed** (3 warnings: EOL `google.generativeai`, deprecated starlette TestClient/httpx pairing, expected unknown-task_type warning). Provider calls are mocked; no live calls were made.

### Last real commit

- `f11ab07`, **2026-06-19** — "Phase 1b: Rename to RFD_Model_Router, dual-protocol REST :8005 + MCP :8004". Last code change; ~3 months stale. Everything after is directive-queue bookkeeping plus `docs/AUDIT.md`.

## 2. Who calls this

### What the repo itself names

- **No config or code names a caller.** The docs name only *parallel* routers and *planned* consumers: RFD_Blog_Engine's `blog_engine/infra/model_router.py`, PrivyBot's routing, AgentFlow's planned `packages/models`, and "Tobor specialists" (`docs/directives/Model_Router_Audit_Directive.md` §1, `docs/AUDIT.md` §4). None is confirmed to call `:8004`/`:8005` — they are consolidation candidates, not dependents.

### Overseer pre-check (2026-09-23, per directive §3)

- `rfd-model-router` **is** registered as a live MCP server.
- **No** `model_router` imports in AgentFlow packages.
- **Remaining risk:** runtime callers only — HTTP `POST :8005/route` or MCP SSE `:8004/mcp` (+ `/messages/`). Both listeners bind `0.0.0.0` with no auth, so a caller could be off-host and invisible to any repo-side check. Confirm via connection log on the two ports, the MCP host's client config, and scheduled tasks/lane configs that could hit the endpoint.

### What a host-side deregistration would touch (report only — Robert acts)

1. The `rfd-model-router` entry in the host's MCP client config.
2. Whatever launches the two listeners — console scripts `rfd-model-router` / `rfd-model-router-api`, plus any scheduled task or startup entry holding `:8004`/`:8005`.
3. Any scheduled task, lane config, or agent prompt that calls `POST :8005/route` or the `route_completion` MCP tool.
4. Env vars `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` — only if nothing else on the host uses them (they are not router-specific).
5. `requests.db` — host-local, gitignored; archive or discard with the service (see §3).
6. The GitHub repo itself — archive is Robert's step.

## 3. Salvage list

| Component | Verdict | Destination / reason |
|---|---|---|
| `routing_config.yaml` (task_type→model map) | **salvage** | AgentFlow `packages/models` — the only live routing data; also candidate input for the agent-totals work. |
| `router.py` (`route()`, `_ADAPTERS` registry) | **salvage** | AgentFlow `packages/models` — dispatch/registry shape is the seed code. |
| `adapters/base.py` + anthropic / groq / openrouter adapters | **salvage** | AgentFlow `packages/models` — thin SDK wrappers, worth carrying; openrouter is unused by shipped config but harmless. |
| `adapters/gemini_adapter.py` | **drop** | Uses EOL `google.generativeai`, reports `0,0` tokens; destination should write fresh against `google.genai` — porting this code saves nothing. |
| `api.py` (REST shell) | **drop** | Custom schema, no auth, echoes `str(exc)` to callers; contract recorded in §1 if a service shell is ever wanted. |
| `server.py` (MCP tool) | **drop** | Single-tool shell; the `route_completion` contract is recorded in §1/`docs/AUDIT.md`. |
| `logger.py` (SQLite log) | **drop** | Sync `sqlite3` inside async handlers is an anti-pattern; schema captured in §1 for the agent-totals/cost work. |
| `tests/` (25 tests) | **drop** | Die with the repo; the provider-mocking pattern is worth copying when `packages/models` gets its own suite (recorded in `docs/AUDIT.md`). |
| `docs/AUDIT.md` | **document** | The capability matrix + gaps list is the spec of what `packages/models` must add (auth, fallback, health/quarantine, pricing). |
| `docs/directives/*`, `pyproject.toml`, `uv.lock`, `.gitignore` | **drop** | Queue artefacts and packaging; no reuse value. |
| `requests.db` (host-local, not in repo) | **document** | Historical per-task token counts may feed the agent-totals work — host-side decision for Robert before the service stops. |

## 4. What rolls into AgentFlow's models package

`routing_config.yaml` + the `router.py`/`BaseAdapter` dispatch shape + the anthropic/groq/openrouter adapters — roughly the 19-line map and ~100 lines of logic. The REST/MCP shells, the SQLite logger, and the Gemini adapter do not carry. Nothing here provides the health/quarantine feature AgentFlow's spec (OpenClaw retirement step F2) wants — `packages/models` builds that fresh either way.

## 5. Live-caller risk

**Low but unverified.** No in-repo caller, no AgentFlow import (overseer grep), and the non-standard API means no generic OpenAI client can be talking to it — any caller must speak the custom `/route` body or the `route_completion` MCP tool. The only hole: the service is registered as a live MCP server and binds `0.0.0.0`, so a runtime caller on the host or LAN would leave no trace in any repo. One host-side connection check on `:8004`/`:8005` closes it — that check is the difference between this report's verdict and a clean archive.
