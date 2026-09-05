# ADR-005: Own-session Playwright read-side; third-party API as fallback

**Status:** proposed (ratifies with RFC-001) · **Date:** 2026-09-05

## Context
The reference repo reads LinkedIn via Apify actors (paid, third-party,
zero own-account risk). We scrape our own logged-in session (free, private,
freshest, but the account bears the risk).

## Decision
v1 reads via headed, paced, capped Playwright on the user's session
(PRD §8 ramp + stop conditions govern volume). The `RawPost` dataclass is the
sealed contract between discovery and everything downstream, explicitly so a
future `ApifySource` (or any API source) can slot in without touching
extract/qualify/draft.

## Trigger to revisit
If the PRD guardrail trips twice (two LinkedIn warnings), discovery halts and
this ADR is reopened with the API path costed out.
