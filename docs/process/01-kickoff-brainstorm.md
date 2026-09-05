# Stage 1 — Kickoff & brainstorm (whiteboard notes)

**Attendees:** Deepak (PO), Claude (tech lead) · **Date:** 2026-09-05

## Problem statement (agreed wording)

> Recruiters post fresh AI/ML openings on LinkedIn every day, often with a
> direct email. Finding them, filtering out the noise (wrong visa terms, wrong
> role type), and writing a tailored email per post takes hours and gets done
> inconsistently. We want the finding/filtering/drafting automated, while
> keeping every actual send a human decision.

## Whiteboard: approaches considered

| Sticky | Idea | Verdict | Why |
|---|---|---|---|
| A | Scrape LinkedIn **Posts** search on own logged-in session, bounded/headed | **✅ chosen** | Freshest signal; recruiter posts carry direct emails; human-paced keeps account risk bounded |
| B | LinkedIn Jobs tab / job boards (Indeed, etc.) | ❌ parked | Applications go into ATS black holes; no direct recruiter contact — different (worse) funnel |
| C | Official LinkedIn API | ❌ rejected | No consumer API for post search; partner program inaccessible to individuals |
| D | Third-party lead/email databases | ❌ rejected | Cost, staleness, and contacts didn't *ask* to be emailed — recruiter posts with an email did |
| E | Auto-connect + auto-DM on LinkedIn | ❌ rejected hard | Highest ban risk, spammy; violates our "account is the asset" principle |
| F | Auto-send emails | ❌ rejected | Reputation is unrecoverable; Gmail **Drafts as the human gate** costs one click and buys total control |
| G | Always-on cloud daemon | ❌ rejected | Detection risk + can't supervise; bounded local passes while present instead |
| H | RAG over documents for drafting | ❌ rejected (YAGNI) | One resume fits in context; RAG earns a place only at multi-resume (v2) |

## Risk board (RAID)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn restriction/ban | Med (rises with volume) | **Critical** — account runs live interviews | Headed, paced, capped, present; hard stop on any warning; ramp (see PRD) |
| Selector rot breaks discovery | High, recurring | Low | Selectors isolated in one file; fail loud, never scrape garbage |
| LLM hallucinates resume claims | Med | High (credibility with recruiters) | Resume-only context + off-resume-claim flagger + human reads every draft |
| Wrong-recipient / bad email parse | Med | Med | Code-owned regex + de-obfuscation; multi-email or image-email ⇒ manual review |
| Gmail OAuth token churn (testing mode) | High | Low | Runbook procedure; 7-day refresh caveat documented |
| Volume target (25+/wk) triggers LinkedIn defenses | **High if day-one** | Critical | Ramp schedule + stop conditions (PRD §Guardrails) — flagged by eng, accepted by PO |

## Decisions made in the room

1. Staged batch architecture (scrape decoupled from processing) — to be
   formalized as ADR in Stage 3.
2. Human gate = Gmail Drafts; scope `gmail.compose` only.
3. Hard filters in code (auditable), LLM only for relevance + drafting.
4. The existing spike code is the reference implementation, not the final word.

## Open questions → resolved in kickoff poll

- Process depth → **full org treatment** (charter in `README.md`)
- Success metric → **metric tree, all three tracked** (PRD §Metrics)
- Volume → **aggressive 25+/wk steady state, with ramp** (PRD §Guardrails)
