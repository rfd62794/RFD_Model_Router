# RFD_Model_Router: 0 of 6 direction questions answered

## 1. Why this exists

A workspace scan found `RFD_Model_Router` without a finished direction interview -
the questionnaire is the default entry point for every repo, so the swarm files
the questions itself. This directive is assigned to `robert` and stays Queued:
it is never auto-approved and never dispatched.

> Six short questions decide how much of Robert's week a repo may have, whether its work may ever merge automatically, and what must never happen in it. Inferring those from code is guessing.

## 2. The question sheet

Six short questions decide what the swarm does with `RFD_Model_Router`: `hours_per_week`
caps how much of the owner's week it may be offered, `stakes` decides whether a
merge may ever be automatic, and `do_not` is copied verbatim into every
directive generated for it.

To answer: `agentflow direction ask RFD_Model_Router` asks the next unanswered question
and records the reply. In chat, `direction RFD_Model_Router = <answer>` answers the
question being asked.

1. **purpose** - In one sentence, what is this project for?
   One line of free text.
2. **done_when** - What would make it finished, or good enough to leave alone?
   Up to 4 short lines.
3. **do_not** - What should never happen here?
   Up to 4 short lines.
4. **audience** - Who uses it: `me`, `players`, `clients`, `work`, `nobody-yet`
   One of: `me`, `players`, `clients`, `work`, `nobody-yet`
5. **hours_per_week** - How much of your week may it have: `0`, `<1`, `1-3`, `3+`
   One of: `0`, `<1`, `1-3`, `3+`
6. **stakes** - If an agent got it wrong, how bad: `low` (private, revertible), `medium` (public but recoverable), `high` (money, live service, client-visible)
   One of: `low`, `medium`, `high`

Any question may be skipped - answer `-`, `skip`, `none`, `nothing` or `n/a` -
and a skip is recorded, so the question is not asked again.

<!-- queue:start -->
## Queue

| Field | Value |
|---|---|
| Status | Superseded |
| Assigned to | robert |
| Branch | - |
| Base branch | - |

**Status log**
- 2026-09-23 22:20 · backlog-policy · none → Queued — generated from a missing-direction finding; asks the repo's owner - never auto-approved or dispatched
- 2026-09-27 03:53 · robert-claude-laptop · Queued → Superseded — docs/DIRECTION.md already exists on origin/master (a5c5d5e0) - closed in triage 2026-09-27
<!-- queue:end -->
