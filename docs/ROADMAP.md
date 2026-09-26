# Roadmap: RFD_Model_Router

Why these milestones: Robert marked this repo `RETIREMENT PLANNED` on 2026-09-23,
and the completed retirement review (`docs/retirement/RFD_Model_Router.md`) found
it archive-ready conditional on one host-side check that nothing calls
`:8004`/`:8005`. So the milestones are the wind-down path the repo's own docs
already state — close the caller question, land the salvage in AgentFlow
`packages/models`, then deregister and archive — not new features. The retirement
doc doubles as the ledger: each step is proven by the section it appends there.

```yaml roadmap
status: draft            # draft | approved
approved: ""             # "2026-09-22 Robert" once approved
reviewed: "2026-09-24"   # last human or model review - the swarm re-plans when stale
replan_after_days: 14    # reviewed older than this -> stale (default 14)
stop_if: "A live caller is found on :8004 or :8005, or Robert reverses the 2026-09-23 RETIREMENT PLANNED decision - this is a wind-down plan, not a feature roadmap."
revive_if: ""            # parked repos only: what would revive it
milestones:
  - id: M1
    title: Close the caller question - the one gate on archive
    status: active       # pending | active | done | blocked
    exit:                # all must hold for the milestone to be done
      - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Host check"}
      - test: "uv run pytest -q"                       # command exits 0 (run in the repo root)
    steps:
      - id: M1.1
        title: Record the host-side caller check result
        kind: docs       # tests | docs | refactor | fix | feature | design
        size: S          # S < 30 min | M one agent run | L = split it
        value: 5         # 1-5, how much it moves the milestone
        needs: []        # step ids in this roadmap that must be done first
        status: pending  # pending | queued | done
        directive: ""    # filled by the swarm when it creates one
        detail: The retirement verdict is archive-ready conditional on one host-side check (docs/retirement/RFD_Model_Router.md Verdict + section 5): confirm nothing connects to :8004 or :8005 - connection log on both ports, the MCP host client config, and scheduled tasks or lane configs that could hit the endpoint. Robert (or the host) runs the check; this step appends a "## Host check" section to docs/retirement/RFD_Model_Router.md recording the date, what was checked, and the outcome. If a caller is found, stop_if fires and this roadmap is wrong - report it.
        accept:          # at least one - how the swarm proves the step is done
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Host check"}
      - id: M1.2
        title: Record the requests.db disposition
        kind: docs
        size: S
        value: 2
        needs: ["M1.1"]
        status: pending
        directive: ""
        detail: The salvage list marks requests.db (the host-local SQLite request log, gitignored) as "document" - its historical per-task token counts may feed the agent-totals work, and the decision is host-side, before the service stops (docs/retirement/RFD_Model_Router.md section 3 and section 2.3 item 5). Record Robert's call as a "requests.db: archived|discarded - <reason>" line inside the "## Host check" section.
        accept:
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: 'requests\.db: (archived|discarded)'}
  - id: M2
    title: Land the salvage in AgentFlow packages/models
    status: pending
    exit:
      - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Salvage handoff"}
      - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: 'landed: packages/models'}
    steps:
      - id: M2.1
        title: Open the salvage handoff record
        kind: docs
        size: S
        value: 3
        needs: []
        status: pending
        directive: ""
        detail: Append a "## Salvage handoff" section to docs/retirement/RFD_Model_Router.md listing each salvage component from section 3 - routing_config.yaml (the 19-line task_type to model map), router.py plus adapters/base.py (the dispatch and registry shape), and the anthropic, groq, and openrouter adapters - each with its planned destination in AgentFlow packages/models and a "pending" marker. This makes the remaining work visible before archive.
        accept:
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Salvage handoff"}
      - id: M2.2
        title: Port the salvage and record the landing
        kind: refactor
        size: M
        value: 5
        needs: ["M2.1"]
        status: pending
        directive: ""
        detail: The port itself is work in the AgentFlow repo (a directive there): carry the routing_config.yaml map, the router.py/BaseAdapter dispatch shape, and the anthropic/groq/openrouter adapters per the salvage list - roughly the 19-line map and ~100 lines of logic (docs/retirement/RFD_Model_Router.md section 4). The gemini adapter, api.py, server.py, logger.py, and tests are marked drop and do not port. This step is done when each handoff line is updated to "landed: packages/models/..." naming the AgentFlow path or commit.
        accept:
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: 'landed: packages/models'}
  - id: M3
    title: Deregister the service and archive the repo
    status: pending
    exit:
      - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Deregistration"}
      - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Archived"}
    steps:
      - id: M3.1
        title: Record the deregistration list worked
        kind: docs
        size: S
        value: 4
        needs: ["M1.1"]
        status: pending
        directive: ""
        detail: Section 2.3 of docs/retirement/RFD_Model_Router.md lists the host-side deregistration steps for Robert: remove the rfd-model-router entry from the host MCP client config, stop whatever launches the two listeners (console scripts, scheduled tasks, startup entries holding :8004/:8005), clear any scheduled task, lane config, or agent prompt that calls POST :8005/route or the route_completion tool, and check the four provider env vars are still needed elsewhere. This step appends a "## Deregistration" section marking each item done or not-applicable.
        accept:
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Deregistration"}
      - id: M3.2
        title: Record the archive
        kind: docs
        size: S
        value: 3
        needs: ["M3.1", "M2.2"]
        status: pending
        directive: ""
        detail: Archiving the GitHub repo is Robert's step and his alone (docs/retirement/RFD_Model_Router.md section 2.3 item 6) once the caller check is clean, the salvage has landed, and deregistration is worked. This step only records it: append a "## Archived - <date> - Robert" line to the retirement doc so the ledger closes.
        accept:
          - grep: {path: "docs/retirement/RFD_Model_Router.md", pattern: "## Archived"}
```
