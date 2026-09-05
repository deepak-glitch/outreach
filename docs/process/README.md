# Project process charter

How this project is run: full org treatment. Every stage produces a written
artifact and gates on product-owner (you) sign-off before the next stage starts.

## Roles

| Role | Who |
|---|---|
| Product owner / stakeholder | Deepak |
| Tech lead / eng team | Claude |
| Reviewer of record | Deepak (PR approvals, stage sign-offs) |

## Lifecycle & stage gates

| # | Stage | Artifact | Gate | Status |
|---|---|---|---|---|
| 1 | Kickoff + brainstorm | `01-kickoff-brainstorm.md` | PO reviews notes | ✅ done |
| 2 | Product requirements | `02-prd.md` (v0.2: + skills interface) | PO signs off PRD | 🔶 in review |
| 3 | Architecture whiteboard + RFC | `03-rfc-architecture.md` + `adr/ADR-001…005` | RFC approved | 🔶 in review |
| 4 | Sprint planning | `04-sprint-plan.md` (epics → tickets) | Backlog accepted | ⬜ |
| 5 | Implementation | One PR per ticket, code-reviewed | CI green + review | ⬜ |
| 6 | Test plan + hardening | `05-test-plan.md`, real-data audit | Exit criteria met | ⬜ |
| 7 | Launch | `06-launch-checklist.md`, runbook | Go/no-go review | ⬜ |
| 8 | Retro | `07-retro.md` | — | ⬜ |

## Working agreements

- Decisions that lock architecture get an ADR (`docs/adr/`); everything else
  lives in the stage doc that decided it.
- The existing code on this branch is the **spike** — it proved the pipeline
  end-to-end. Stages 3–5 decide what survives into production as-is, what gets
  reworked, and what gets tests before we trust it.
- No stage skips its gate. "Looks good, next" in the conversation counts as
  sign-off; we record it in the stage table above.
