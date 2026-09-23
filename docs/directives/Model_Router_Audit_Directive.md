# Model Router audit: what it is, who needs it, absorb or consume

## 1. Why this exists

Robert, 2026-09-23: "RFD Model Router is complicated, I don't know if it should be absorbed, or
AgentFlow become a Consumer of it." Multi-provider model routing exists in at least four places:
this repo (FastAPI REST :8005 + MCP :8004, routes by task type to Anthropic/Groq/Gemini/OpenRouter/
RunPod, fallbacks, pricing, throttling, SQLite logs), RFD_Blog_Engine's `blog_engine/infra/model_router.py`,
PrivyBot's routing, and AgentFlow's planned `packages/models` (OpenClaw retirement spec, step F2:
model health + quarantine registry). This audit measures, it decides nothing.

## 2. The work

Read everything in this worktree: `rfd_model_router/`, `routing_config.yaml`, `tests/`, `pyproject.toml`.
Write `docs/AUDIT.md` with:

1. **What exists:** every module, route and MCP tool, one line each with the file; the config
   schema; providers and which are paid vs free-tier; what the SQLite log records; test count
   (`uv run pytest -q`).
2. **Capabilities matrix** - rows: task-type routing, fallback chain, per-model pricing, spend cap,
   rate-limit/throttle, health check or quarantine of failing models, request logging,
   OpenAI-compatible API, MCP. Columns: this repo (yes/partial/no with file refs), and the questions
   the others must answer (leave them for Claude to fill from those repos - write `?`).
3. **Gaps and risks:** anything that could spend money without a cap, secrets handling, what breaks
   if a provider is down, anything untested.
4. **The three options, stated neutrally:** (a) AgentFlow absorbs it as a package, (b) it stays a
   service and AgentFlow/Blog Engine/Tobor specialists call it, (c) retire it in favour of
   AgentFlow `packages/models`. For each: what changes, what is deleted, what it costs.

## 3. What NOT to do

- No code changes. No network calls, no provider calls (tests must already mock them).
- Never print or copy any key or `.env` content.

## 4. Completion criteria

- [ ] `docs/AUDIT.md` exists with all four sections, every claim citing a file.

## 5. Rules for this run

- This run is **NON-INTERACTIVE**. Any tool call that needs a confirmation is rejected outright and
  the run ends mid-task. Do not install, download or fetch anything. Do not read outside this
  working directory, and do not use a search, memory or web tool.
- Never use `git -C` or `git -c`; run git from the worktree.
- These are the only commands available to you: `uv run pytest`, `git status`, `git diff`,
  `git log`, `git show`, `git add`, `git commit`, `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `mkdir`.
- Work only on your `directive/<slug>` branch. **Never commit to main, never push, never deploy.**
- Update this directive's Status row when you finish or stop partway.
- If a tool call is genuinely blocked, stop and write why in the Status row.

<!-- queue:start -->
## Queue

| Field | Value |
|---|---|
| Status | Done |
| Assigned to | devin |
| Branch | directive/rfd-model-router-model-router-audit-directive |
| Base branch | - |
| Base commit | 44c32842e613e708e790ccedb5486537c0427ae7 |

**Status log**
- 2026-09-23 07:34 · robert-claude · none → Queued — Robert 2026-09-23: yes, audit the Model Router
- 2026-09-23 07:34 · robert-claude · Queued → Approved
- 2026-09-23 07:34 · dispatcher · Approved → In progress — dispatched devin in C:\GitHub\.worktrees\RFD_Model_Router--rfd-model-router-model-router-audit-directive; base origin/master (local master differs)
- 2026-09-23 07:38 · devin · In progress → Review
- 2026-09-23 10:54 · robert-claude · Review → Done
<!-- queue:end -->
