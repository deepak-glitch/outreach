# PRD — Job-post outreach pipeline v1

**Status:** in review · **Owner:** Deepak · **Author:** Claude (tech lead)
**Doc history:** v0.1 2026-09-05 first draft from kickoff decisions ·
v0.2 2026-09-05 PO direction: expose the pipeline as Claude Code skills
(reference: sergebulaev/linkedin-skills) — added F12, updated G5

## 1. Background & problem

See brainstorm notes (`01-kickoff-brainstorm.md`). One user (Deepak), searching
for AI/ML engineering roles. Recruiter posts on LinkedIn with direct emails are
the highest-signal channel; working them manually is slow and inconsistent.

## 2. Goals

- G1: Surface fresh (≤24h) recruiter/hiring posts matching configured searches.
- G2: Qualify them against explicit, auditable personal rules (work-auth,
  employment type, location/remote) plus an LLM relevance screen.
- G3: For email-contact posts, produce a resume-grounded draft in Gmail Drafts
  with resume.pdf attached — review queue is Gmail itself.
- G4: Preserve every non-email lead (DM/link) with full extracted data as v2
  candidates.
- G5: Operable conversationally from Claude Code via SKILL.md skills — "find
  new posts", "process and show me the drafts", "why was this one rejected" —
  with the deterministic pipeline underneath, not replaced.

## 3. Non-goals (v1)

Auto-connect/auto-DM · auto-send email · always-on daemon · cloud hosting ·
RAG/multi-resume · reply tracking (v2) · any UI beyond CLI + Gmail + SQLite.

## 4. Users & stories

Single user, the job seeker.

- As the job seeker, I run one command while at my machine and get fresh raw
  posts captured without risking my account.
- As the job seeker, I run one command and every captured post is either
  drafted, skipped-with-reason, or held for my manual review — nothing silent.
- As the job seeker, I open Gmail Drafts, read each draft, and send only the
  ones I approve, unedited or edited.
- As the job seeker, I can query why any post was rejected weeks later.

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| F1 | Bounded discover pass: hard post cap, bounded wall-clock window, jittered human pacing, headed browser, Ctrl-C kill switch | P0 |
| F2 | Dedup by canonical post URL; re-runs idempotent | P0 |
| F3 | Extraction to structured fields incl. verbatim work-auth wording | P0 |
| F4 | contact_method ∈ {email, dm, link, none, unknown}; email de-obfuscation; ambiguous ⇒ low_confidence ⇒ manual review hold | P0 |
| F5 | Hard filters in code from `rules.json`, each rejection logged with reason | P0 |
| F6 | LLM relevance screen only for hard-filter survivors | P0 |
| F7 | Draft grounded solely in resume.txt; off-resume claims flagged | P0 |
| F8 | Gmail draft via `gmail.compose` scope only, resume.pdf attached | P0 |
| F9 | Per-post failure isolation (`status=error`, batch continues); hard-fail on auth errors | P0 |
| F10 | `--dry-run` for process; per-run structured logs; status CLI | P1 |
| F11 | All tunables in `config/`, no magic numbers | P1 |
| F12 | Skills layer (`skills/*/SKILL.md`, agentskills.io style) wrapping the pipeline: discover, process, review, status/explain, tune-rules — every publish-adjacent action still human-gated | P0 |

## 6. Non-functional requirements

- **Account safety first:** any LinkedIn warning ⇒ full stop (see guardrails).
- **Auditability:** the SQLite `posts` table is the system of record; every
  state transition timestamped with a human-readable reason.
- **Cost:** cheap model for classify/qualify; strong model only for drafting.
- **Reproducibility:** clean checkout + README ⇒ working install.
- **Privacy:** `.userdata/` (live session) and `.secrets/` never leave the
  machine, never committed.

## 7. Success metrics (metric tree — PO chose to track all three)

**Headline:** recruiter replies.

| Tier | Metric | Target (first 4 weeks live) |
|---|---|---|
| North star | Recruiter replies to sent outreach | ≥2/week by week 4 |
| Primary | Send-worthy drafts (sent with ≤ minor edits) | ≥15/week at full ramp; <20% discarded |
| Primary | Time spent on job-search outreach | ≤2h/week (from ~8-10h manual) |
| Guardrail | LinkedIn warnings/interstitials | **0** — any occurrence pauses discovery |
| Guardrail | Drafts with off-resume claims reaching Gmail unflagged | 0 known incidents |
| Guardrail | Wrong-recipient drafts | 0 sent (human gate catches; measure flag rate) |

Measurement: replies counted manually in Gmail (v1); pipeline counts from the
`posts` table and logs.

## 8. Volume target & ramp (PO decision + eng guardrail)

PO target: **aggressive, 25+ sends/week steady state.** Eng flagged that
day-one aggressive volume is the single biggest threat to the critical
guardrail (account safety). Agreed compromise recorded here:

| Phase | Discover caps | Expected sends | Advance when |
|---|---|---|---|
| Week 1 (live) | 25 posts/run, 3 runs/wk | ~5 | zero warnings, extraction accuracy ≥90% on hand-check |
| Week 2 | 30/run, 5 runs/wk | ~10-15 | zero warnings |
| Week 3+ | 40/run, daily | **25+** | zero warnings, sustained |

**Stop conditions (non-negotiable):** any LinkedIn warning/captcha/unusual-
activity page ⇒ discovery paused ≥48h, cap halved on resume; second occurrence
⇒ discovery paused until process review. Gmail sends are unaffected (human
clicks), but draft volume follows discovery down.

## 9. Milestones

- M1: PRD signed off ← **we are here**
- M2: Architecture RFC + ADRs approved
- M3: Sprint plan accepted; implementation PRs land with review + CI
- M4: Real-data dry-run audit passes exit criteria (test plan doc)
- M5: Go-live at Week-1 ramp caps; first human-sent outreach
- M6: Full ramp (25+/wk) or documented reason we stopped earlier

## 10. Out-of-scope risks accepted by PO

- LinkedIn ToS exposure of scraping own feed at human pace: accepted, bounded
  by the guardrails above; account health is the canary.
- Testing-mode OAuth token churn: accepted for v1 (runbook procedure).

## Sign-off

- [ ] Product owner (Deepak) — *pending; approving this doc advances us to Stage 3 (architecture RFC)*
