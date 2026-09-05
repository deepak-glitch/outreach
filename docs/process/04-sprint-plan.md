# Stage 4 — Sprint plan

Derived from RFC-001 §7 (gaps the skills layer exposes in the spike).
One ticket = one PR = one reviewable unit.

## EPIC-1 — Engine support for the skills layer

| ID | Ticket | Acceptance criteria | Status |
|---|---|---|---|
| ENG-1 | Machine-readable output + preflight + guardrail | `--json` on every subcommand; `preflight` reports per-stage readiness; PRD §8 stop conditions enforced in code with unit tests | ✅ done |
| ENG-2 | Persist draft subject/body in the DB | `outreach-review` can read a draft without calling Gmail; schema adds `draft_subject`/`draft_body`; migration is idempotent | ⬜ |
| ENG-3 | Re-qualify stored posts | `process --stage qualify --requeue` re-runs verdicts after a rules change without re-scraping | ⬜ |

## EPIC-2 — Skills

| ID | Ticket | Acceptance criteria | Status |
|---|---|---|---|
| SKILL-1 | `outreach-discover` | Runs preflight, confirms presence, runs a capped pass, interprets `stop_reason`, refuses to work around the guardrail | ✅ done |
| SKILL-2 | `outreach-process` | Dry-run first, presents drafts in chat, real run only on explicit approval | ⬜ |
| SKILL-3 | `outreach-review` | Critiques drafts against resume.txt; flags off-resume claims; needs ENG-2 | ⬜ |
| SKILL-4 | `outreach-status` | Explains any post's verdict from the audit trail | ⬜ |
| SKILL-5 | `outreach-tune` | Edits rules/keywords, shows a diff, previews effect; needs ENG-3 | ⬜ |

## EPIC-3 — Quality

| ID | Ticket | Acceptance criteria | Status |
|---|---|---|---|
| QA-1 | Unit tests for safety-critical logic | guardrail, preflight, discover contract covered | ✅ done (27 tests) |
| QA-2 | CI on push | tests + compile run on the branch | ⬜ |
| QA-3 | Real-data audit | PRD M4 exit criteria met on a hand-checked sample | ⬜ |

## Definition of done (every ticket)

Tests pass · no regression in the pipeline regression test · docs updated ·
committed with a message explaining *why*, not just what.

## SKILL-1 closing notes

Two things emerged during implementation that were not in the RFC:

1. **The guardrail had nowhere to live.** PRD §8's stop conditions existed only
   as prose in a doc. A rule that depends on a tired person remembering it at
   11pm is not a control, so it became `src/guardrail.py` with state in
   `data/guardrail.json` — deliberately plain text, because the only way past a
   block should be a person opening it and deciding.
2. **`stop_reason` matters more than the post count.** The original
   `run_discover` returned an int, which cannot distinguish "captured 3 and
   finished cleanly" from "captured 20 and hit a security check". The skill
   needs that distinction to know whether to celebrate or stop, so discovery
   now returns a typed `DiscoverResult`.
