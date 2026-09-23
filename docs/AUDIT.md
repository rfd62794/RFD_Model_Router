# RFD Model Router — Audit

Date: 2026-09-23. Scope: this repo only, at commit 44c3284. This audit measures; it decides nothing.

**Headline finding:** the code is much smaller than the charter description implies. The directive
brief describes "fallbacks, pricing, throttling" and a RunPod provider. None of those exist in the
code: there is no fallback chain, no pricing, no throttling, and no RunPod adapter. What exists is a
single-provider-per-task-type dispatcher behind two network front doors (REST + MCP), with a SQLite
request log.

## 1. What exists

### Modules (one line each)

| File | What it is |
|---|---|
| `rfd_model_router/router.py` | Core: loads `routing_config.yaml`, maps task_type → provider+model, instantiates adapter, calls `complete()`. Unknown task_type warns and falls back to the `default` entry only. |
| `rfd_model_router/api.py` | FastAPI app "RFD Model Router API"; POST `/route`; uvicorn on `0.0.0.0:8005` (`api.py:76`). |
| `rfd_model_router/server.py` | MCP server via `FastMCP("rfd-model-router")`, SSE transport on `0.0.0.0:8004` (`server.py:8,41`). |
| `rfd_model_router/logger.py` | SQLite logger; `init_db()` + `log_request()`; DB at `requests.db` in repo root (`logger.py:5`). |
| `rfd_model_router/adapters/base.py` | `BaseAdapter` ABC: `complete(model, messages, system_prompt) -> (text, in_tokens, out_tokens)`. |
| `rfd_model_router/adapters/anthropic_adapter.py` | Anthropic SDK; env `ANTHROPIC_API_KEY`; hardcodes `max_tokens=1024` (`anthropic_adapter.py:18`). |
| `rfd_model_router/adapters/groq_adapter.py` | Groq SDK; env `GROQ_API_KEY`; system prompt prepended as a `system` message. |
| `rfd_model_router/adapters/gemini_adapter.py` | `google.generativeai` (deprecated pkg); env `GEMINI_API_KEY`; returns `0,0` for token counts (`gemini_adapter.py:29`). |
| `rfd_model_router/adapters/openrouter_adapter.py` | OpenAI SDK pointed at `https://openrouter.ai/api/v1`; env `OPENROUTER_API_KEY`. Present but unused by the shipped config. |

### Routes and MCP tools

| Surface | Endpoint/tool | File |
|---|---|---|
| REST | `POST /route` — body `{task_type, messages, system_prompt?}` → `{completion, provider, model, tokens{input,output}}`; errors → HTTP 500 with `str(exc)` in the body | `rfd_model_router/api.py:28-56` |
| REST | Catch-all exception handler → 500 JSON `{detail}` | `rfd_model_router/api.py:59-61` |
| MCP | tool `route_completion(task_type, messages, system_prompt?) -> str` — returns only the completion text; provider/model/tokens are logged but not returned | `rfd_model_router/server.py:11-36` |

Entry points: `rfd-model-router` → `server:main` (MCP :8004), `rfd-model-router-api` → `api:main` (REST :8005) (`pyproject.toml:17-19`).

### Config schema (`routing_config.yaml`)

Top-level YAML mapping of `task_type -> {provider: str, model: str}`. `provider` must be a key of
`_ADAPTERS` in `router.py:14-19` (`anthropic|groq|gemini|openrouter`). `default` is a reserved
task_type used as the fallback (`router.py:43-46`). Shipped entries:

- `code_transformation` → groq / llama-3.1-70b-versatile
- `code_construction` → anthropic / claude-haiku-4-5-20251001
- `content` → gemini / gemini-2.0-flash-exp
- `directive` → anthropic / claude-sonnet-4-6
- `default` → anthropic / claude-haiku-4-5-20251001

No schema validation beyond "must be a YAML mapping" (`router.py:25-26`); a missing `provider`/`model`
key or a typo surfaces as a runtime `KeyError`/`ValueError`.

### Providers: paid vs free-tier

| Provider | Adapter | Paid/free | Notes |
|---|---|---|---|
| Anthropic | yes | Paid | Claude models have no free tier; `code_construction`, `directive`, `default` all route here. |
| Groq | yes | Free tier exists | Generous free tier with rate limits; paid tier available. Used for `code_transformation`. |
| Gemini | yes | Free tier exists | `gemini-2.0-flash-exp` is an experimental model on the free AI Studio tier. Used for `content`. |
| OpenRouter | yes (adapter only) | Paid | Per-token aggregator; no config entry uses it. |
| RunPod | **no adapter exists** | — | Mentioned in the directive brief; absent from `rfd_model_router/adapters/` and `_ADAPTERS` (`router.py:14`). |

API keys come from env vars only (`ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`,
`OPENROUTER_API_KEY`); there is no `.env` loading and no key-presence check at startup — a missing
key fails on first request, not at boot.

### What the SQLite log records

`requests.db` (gitignored, `.gitignore:6`), table `requests` (`logger.py:11-24`):
`id, timestamp (UTC ISO), task_type, provider, model, input_tokens, output_tokens, duration_ms, success`.
On failure the provider/model are written as the literal strings `"unknown"`, losing which provider
failed (`api.py:53`, `server.py:33`). All logging exceptions are swallowed (`logger.py:27-28,60-61`,
`api.py:42-43`, `server.py:27-28`). `aiosqlite` is a declared dependency (`pyproject.toml:14`) but
unused — `logger.py` uses synchronous `sqlite3` inside async handlers.

### Test count

`uv run pytest -q`: **25 passed**, 0 failed (3 warnings: deprecated `google.generativeai` package,
deprecated starlette TestClient/httpx pairing, expected unknown-task_type warning).

## 2. Capabilities matrix

"Others" columns are left `?` for Claude to fill in from those repos
(RFD_Blog_Engine `blog_engine/infra/model_router.py`, PrivyBot routing, AgentFlow `packages/models`).

| Capability | This repo | Blog Engine | PrivyBot | AgentFlow `packages/models` |
|---|---|---|---|---|
| Task-type routing | **Yes** — task_type → provider+model map (`router.py:37-53`, `routing_config.yaml`) | ? | ? | ? |
| Fallback chain | **No** — only task_type → `default` fallback (`router.py:43-46`); no provider failover if the call itself fails | ? | ? | ? |
| Per-model pricing | **No** — token counts logged but no price table or cost math anywhere | ? | ? | ? |
| Spend cap | **No** — nothing inspects cumulative cost or blocks requests | ? | ? | ? |
| Rate-limit / throttle | **No** — no throttling code; relies entirely on provider-side limits | ? | ? | ? |
| Health check / quarantine | **No** — failures recorded in `requests.success` but nothing reads them back to route around a sick provider | ? | ? | ? |
| Request logging | **Yes** — SQLite `requests` table (`logger.py`); silent-fail, never rotated | ? | ? | ? |
| OpenAI-compatible API | **No** — `/route` is a custom schema, not `/v1/chat/completions`; OpenRouter *adapter* uses the OpenAI SDK outbound, but no inbound OpenAI-compatible surface | ? | ? | ? |
| MCP | **Yes** — FastMCP SSE server, one tool `route_completion` (`server.py`) | ? | ? | ? |

## 3. Gaps and risks

**Unbounded spend.**
- Both listeners bind `0.0.0.0` (`api.py:76`, `server.py:41`) with **no authentication** — any host
  that can reach :8004/:8005 can run billable Anthropic calls. `default` and `directive` both route
  to paid Claude models (`routing_config.yaml:13-19`).
- No spend cap, no pricing table, no per-caller accounting — the DB cannot attribute spend to a caller.
- Anthropic `max_tokens=1024` caps output per call (`anthropic_adapter.py:18`) but nothing caps call
  rate or count.

**Secrets handling.**
- Keys are read from env vars only — no keys in the repo, no `.env` file present, nothing logged.
  That is the good news. The bad news: a missing key produces a first-request failure, not a boot-time
  error, and the 500 response body echoes `str(exc)` (`api.py:56`, `api.py:61`), which can leak
  provider error detail (request IDs, sometimes key fragments in SDK messages) to an unauthenticated
  caller.

**Provider-down behaviour.**
- If the configured provider is down, the request dies: 500 to the REST caller, exception to the MCP
  caller. There is no retry, no alternate provider, no circuit breaker (`router.py:50-52` is a single
  `adapter.complete` call).
- The failure is logged with provider/model = `"unknown"` (`api.py:53`, `server.py:33`), so the log
  cannot even tell you *which* provider was down — only that `task_type` failed.
- `init_db` and `log_request` swallow all exceptions (`logger.py:27-28,60-61`): a broken DB is
  invisible and requests still succeed — logging is best-effort by design but nothing surfaces that
  it stopped.

**Untested / weakly covered.**
- `server.py` MCP wiring is exercised only indirectly (`tests/test_router.py:69-79` calls the tool
  function, not the transport); no test touches SSE.
- No test for a provider *call* raising — the 500 path in `api.py:50-56` and the re-raise path in
  `server.py:30-36` are untested.
- No test for malformed config entries (missing `provider`/`model` keys, non-mapping YAML).
- `gemini_adapter.py` uses the end-of-life `google.generativeai` package (FutureWarning in the test
  run) and reports `0,0` tokens, so Gemini spend is untracked (`gemini_adapter.py:29`).
- `openrouter_adapter.py` has a test but no config entry uses it — dead in practice.
- Sync `sqlite3` inside async handlers (`logger.py` used from `api.py`/`server.py`) can block the
  event loop under load.

## 4. The three options, stated neutrally

### (a) AgentFlow absorbs it as a package

- **What changes:** `rfd_model_router/` moves into AgentFlow as `packages/models` seed code —
  keep `router.py`, the four adapters, `routing_config.yaml` semantics. The REST/MCP servers and
  SQLite logger become optional shells or get replaced by AgentFlow's own plumbing.
- **What is deleted:** this repo eventually; possibly `server.py`/`api.py`/`logger.py` if AgentFlow
  provides serving + observability. Blog Engine's parallel `model_router.py` and PrivyBot's routing
  get consolidated onto the same package (per the `?` column above, that needs verifying there).
- **What it costs:** an in-process import per consumer — no network hop, no port management. But
  every consumer now needs every provider's SDK + keys installed locally, config becomes file-based
  per deployment, and a bugfix ships to N consumers instead of one service. AgentFlow `packages/models`
  was already planned (OpenClaw retirement spec step F2: health + quarantine) — absorbing gives that
  work a starting codebase that is ~180 lines of real logic.

### (b) It stays a service; AgentFlow / Blog Engine / Tobor specialists call it

- **What changes:** nothing inside this repo necessarily; consumers switch from local routing to
  HTTP `POST :8005/route` or MCP `:8004`. The repo's own gaps become the worklist: auth, fallback
  chain, health/quarantine, pricing — all currently absent (Section 2).
- **What is deleted:** Blog Engine's `blog_engine/infra/model_router.py` and PrivyBot's equivalent
  (if they exist as described); duplicated adapters elsewhere.
- **What it costs:** a network hop + a shared point of failure for every consumer; one place to add
  auth/caps/health so fixes land once; keys live only on the router host. Realistically this option
  requires building the missing Section-2 capabilities to be worth the hop — today the service adds
  only a YAML map and a log over calling the SDKs directly.

### (c) Retire it in favour of AgentFlow `packages/models`

- **What changes:** AgentFlow builds `packages/models` fresh per the retirement spec (health +
  quarantine registry); this repo is archived. Consumers adopt AgentFlow's package directly.
- **What is deleted:** this entire repo — ~180 lines of logic plus tests — and the two running
  ports (:8004, :8005). The task_type→model map (`routing_config.yaml`) is the only artefact worth
  porting; it's 19 lines.
- **What it costs:** the least code survives. The MCP tool and REST endpoint disappear, so anything
  that calls them today (check who, if anyone) must migrate; AgentFlow carries the full build cost
  with no reuse except the config shape and adapter pattern. Nothing here is irreplaceable — but
  nothing in the repo yet provides the F2 health/quarantine feature AgentFlow wants either, so
  "absorb" and "retire + rebuild" differ mainly in how much of ~180 lines gets carried over.

---

*Audit method: read every file in the worktree; ran `uv run pytest -q` (25 passed); no provider or
network calls made; no secrets read or printed.*
