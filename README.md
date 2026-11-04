# RFD Model Router

A small task-type router for LLM calls. You tag each request with a task type (for example `code_construction` or `content`), and the router sends it to the provider and model mapped to that task in one YAML file. It serves the same router two ways: a REST endpoint and an MCP server, and it logs every request to SQLite.

> **Status: retired.** This repo is kept public as a small, readable standalone piece. Its routing map and adapter shape were marked for salvage into the model layer of [AgentFlow](https://rfditservices.com/projects/agentflow/) in September 2026. No new features are planned here.

## How it works

```
caller ──► POST /route (REST, :8005) ──┐
                                       ├─► router.py ──► routing_config.yaml
caller ──► route_completion (MCP, :8004)┘        │        (task_type → provider + model)
                                                 ▼
                                   adapter: anthropic | groq | gemini | openrouter
                                                 │
                                                 ▼
                                   requests.db (SQLite log: task, provider, model,
                                                tokens, duration, success)
```

- **One map, one place to change models.** `routing_config.yaml` maps each task type to a provider and model. An unknown task type falls back to the `default` entry, with a warning.
- **Thin adapters.** Each provider is one class with one method, `complete(model, messages, system_prompt)`, returning the text and token counts. Adding a provider means adding one adapter and one line in the adapter table.
- **Two front doors.** `rfd-model-router-api` runs a FastAPI app with `POST /route`. `rfd-model-router` runs an MCP server (SSE) with one tool, `route_completion`.
- **Request log.** Every call writes a row to `requests.db`: timestamp, task type, provider, model, input and output tokens, duration and success.

The shipped map:

| Task type | Provider | Model |
|---|---|---|
| `code_transformation` | Groq | llama-3.1-70b-versatile |
| `code_construction` | Anthropic | claude-haiku-4-5 |
| `content` | Gemini | gemini-2.0-flash-exp |
| `directive` | Anthropic | claude-sonnet-4-6 |
| `default` | Anthropic | claude-haiku-4-5 |

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/rfd62794/RFD_Model_Router
cd RFD_Model_Router
uv sync

# Set the keys for the providers your map uses
export ANTHROPIC_API_KEY=...
export GROQ_API_KEY=...
export GEMINI_API_KEY=...

uv run rfd-model-router-api        # REST on http://localhost:8005
```

```bash
curl -s http://localhost:8005/route \
  -H "Content-Type: application/json" \
  -d '{"task_type": "content",
       "messages": [{"role": "user", "content": "Write a one-line product tagline."}]}'
```

Response:

```json
{"completion": "...", "provider": "gemini", "model": "gemini-2.0-flash-exp",
 "tokens": {"input": 0, "output": 0}}
```

To run it as an MCP server instead: `uv run rfd-model-router` (SSE on port 8004, tool `route_completion`).

## Tests

```bash
uv run pytest
```

25 tests. Provider calls are mocked, so the suite makes no network calls and needs no keys.

## Limits, stated plainly

This is a dispatcher, not a gateway. The repo's own [audit](docs/AUDIT.md) lists what it does not do:

- No fallback to another provider when a call fails. The request fails.
- No pricing, spend cap or rate limiting.
- No authentication. Both servers bind to `0.0.0.0`, so run it only on a machine or network you trust.
- The REST schema is its own, not OpenAI-compatible.
- The Gemini adapter uses the older `google-generativeai` package and reports zero tokens.

Those gaps are why the routing moved into AgentFlow, where health checks and budgets live. The [retirement notes](docs/retirement/RFD_Model_Router.md) record what moved and what was dropped.
