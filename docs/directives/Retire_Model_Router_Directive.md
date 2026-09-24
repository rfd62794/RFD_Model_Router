# RFD_Model_Router: retirement review + dependency audit

**Context.** Robert marked RFD_Model_Router `RETIREMENT PLANNED` on
2026-09-23 (Portfolio `projects.yaml` — agentstack MCP sweep). Retirement
rolls useful machinery into `Agents`/`AgentFlow`, then Robert archives the
repo. This directive produces the audit and salvage list — it does **not**
archive, deregister, or delete anything.

## 1. Why

RFD_Model_Router is a task-based LLM router with an OpenAI-compatible API —
registered as a live MCP server (`rfd-model-router`). The open question is
whether AgentFlow's agent lanes route through it: the overseer's code sweep
found **no** imports of it in AgentFlow packages, but lanes may call it over
HTTP/MCP at runtime. If anything live routes through it, retirement waits —
the report must make that call obvious.

## 2. Scope

This repo is cloned — the worktree **is** RFD_Model_Router; audit in place.

1. Audit: README/entry points, what the router serves (routes, model map,
   API surface), test state, last real commit.
2. Dependents the run can see: its own config/docs naming callers; note for
   the report that host-side checks (MCP registration, AgentFlow lane
   configs, scheduled tasks hitting the router endpoint) were pre-checked by
   the overseer — see §3 — and list what a host-side deregistration would
   touch.
3. Salvage list: per component — `salvage` (destination named; the model
   catalog/routing table may belong in `AgentFlow`'s models package or the
   agent-totals work), `document`, or `drop`.
4. Write the audit to `docs/retirement/RFD_Model_Router.md` **in this repo**.

## 3. Dependents (overseer pre-check, 2026-09-23)

- Registered as a live MCP server: `rfd-model-router` — **yes**.
- No `model_router` imports found in AgentFlow packages (2026-09-23 grep);
  runtime callers via HTTP/MCP are the remaining risk — the report should
  name the endpoint/port so a host-side check can confirm nothing calls it.

## 4. What NOT to do

- Do not archive, delete, deregister, stop the service, or edit configs.
- Do not make live calls to the router.
- Never use `git -C` / `-c` / `--git-dir` / `--work-tree` flag forms.
- Report only. Robert archives.

## 5. Verification

- `docs/retirement/RFD_Model_Router.md` exists, verdict per component, an
  explicit "who calls this" section.
- If the repo has a test suite, run `uv run pytest -q` (or its own runner)
  and record the count — do not fix failures.

## Sandbox needs

- `Exec(uv run pytest -q)`
  (run only if the repo has a suite — declared so the option exists)

## 6. Rules for this run

- NON-INTERACTIVE: any tool call needing confirmation ends the run.
- Work on branch `directive/rfd-model-router-retire-model-router-directive`
  from `master`.
- One or two commits on the branch; never commit to `master`, never push it.
- If something is genuinely blocked, stop and write why in the Status row.

## 7. Completion criteria

- [ ] `docs/retirement/RFD_Model_Router.md` committed on the branch.
- [ ] "Who calls this" section filled; test count recorded if a suite exists.
- [ ] Status row → **Review** with the branch named.

## 8. Report

Verdict per component, live-caller risk, what rolls into AgentFlow's models
package, `archive-ready` or `keep`.

<!-- queue:start -->
## Queue

| Field | Value |
|---|---|
| Status | Approved |
| Assigned to | devin |
| Branch | directive/rfd-model-router-retire-model-router-directive |
| Base branch | - |
| Base commit | 9c65f1cb |

**Status log**
- 2026-09-23 21:13 · devin-overseer · none → Draft — agentstack retirement sweep (Robert, 2026-09-23)
- 2026-09-23 21:18 · devin-overseer · Draft → Queued
- 2026-09-23 21:19 · devin-overseer (delegated) · Queued → Approved
<!-- queue:end -->
