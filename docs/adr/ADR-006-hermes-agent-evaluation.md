# ADR-006: Hermes Agent — evaluated, deferred to v2

**Status:** proposed (recommendation: defer) · **Date:** 2026-09-05
**Evaluated:** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

## Context

PO asked whether Hermes Agent (Nous Research) is free, whether it would speed
up the outreach process, and whether we may modify it.

### Findings of fact

| Question | Finding |
|---|---|
| Cost | **Free.** MIT License, © 2025 Nous Research. Self-hosted, one-line install, runs on a $5 VPS or Docker. |
| Modification rights | **Unrestricted.** MIT grants use, copy, modify, merge, publish, distribute, sublicense, sell. Conditions: keep the copyright + license text in copies/substantial portions; no warranty. |
| Model lock-in | **None.** Provider-agnostic — Nous Portal, OpenRouter, OpenAI, own/local endpoint. Nous Portal subscription is optional. |
| Capabilities | Persistent memory (FTS5 session search + LLM summarization), autonomous skill creation, built-in cron scheduler with delivery, messaging gateways (Telegram/Discord/Slack/WhatsApp/Signal/CLI), 40+ built-in tools. |
| Skill format | **SKILL.md, agentskills.io-compatible — the same standard ADR-004 already selected.** |

### Where it would and would not make us faster

Decomposing where wall-clock time actually goes in our funnel:

| Stage | Current cost | Hermes impact |
|---|---|---|
| LinkedIn discovery | Deliberately slow (jittered pacing, caps) | **None — and must stay none.** Pacing is a safety dial, not a performance problem. Speeding it is the one thing we must not do. |
| extract → qualify → draft | Seconds to minutes, already automated | Negligible — not the bottleneck |
| Human review in Gmail | The real remaining human time | Doesn't remove it (by design we don't want it removed), **but its Telegram gateway could move review to your phone** — genuine friction win |
| Being at the desk to start a pass | Requires presence | `process` never touches LinkedIn (SQLite + LLM + Gmail drafts only), so **cron-scheduling `process` is safe** and would leave drafts waiting. `discover` must stay attended. |
| Draft quality over time | Static | Its memory loop could learn from which drafts you edit or discard — this is our existing v2 backlog item |

### Why not adopt for v1

1. **Direct tension with our top guardrail.** Hermes is engineered for autonomy
   (cron, self-authored skills, unattended delivery); its public docs do not
   describe an approval gate. Our core safety properties are human presence
   during LinkedIn access (ADR-005) and no auto-send (ADR-002). Any gate would
   be ours to build and enforce, not something we inherit.
2. **Blast radius.** An autonomous runtime with access to a live LinkedIn
   session (`.userdata/`) and `gmail.compose` is a materially larger security
   surface than two human-run commands.
3. **Ops weight vs. payoff.** Gateway process, memory store, 40+ tools and a
   VPS, to orchestrate a single-user pipeline that today is two commands.
4. **It replaces none of our engine.** LinkedIn discovery and resume-grounded
   drafting are still 100% ours to write either way.
5. **v1's bottleneck is accuracy and account safety, not orchestration.**

### Why we lose nothing by waiting

ADR-004 already committed us to agentskills.io `SKILL.md` folders. Hermes
consumes that same format. **Our skills are therefore portable to Hermes at
near-zero cost whenever we want them there** — picking the standard bought us
the option without picking the runtime.

## Decision

Do not adopt Hermes Agent for v1. Keep the deterministic engine + Claude Code
skills (RFC-001). Record three concrete v2 jobs it is a strong candidate for:

- **V2-A** Mobile review/approve gateway (Telegram) for the Gmail-draft queue.
- **V2-B** Scheduled `process` runs (never `discover`) so drafts are waiting.
- **V2-C** Outcome memory — learn from edited/discarded drafts to improve drafting.

Revisit after M5 (go-live) when real usage shows whether desk-bound review is
the friction that matters.

## If/when we do adopt: fork vs. depend

MIT permits a fork outright. Recommendation is still to **depend and wrap, not
fork** — a fork of a fast-moving agent runtime means inheriting merge pain
forever. Fork only if we must change core behavior (e.g. strip autonomy),
and if so, keep the delta small and documented. Either path requires shipping
the MIT text and Nous copyright line with anything we distribute.

## Consequences

- No new dependency in v1; no change to RFC-001.
- Three v2 backlog items created with a named candidate implementation.
- Our SKILL.md format choice is now load-bearing for portability — do not
  drift from the agentskills.io convention without reopening this ADR.
