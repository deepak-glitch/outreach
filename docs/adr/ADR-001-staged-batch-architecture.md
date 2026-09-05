# ADR-001: Staged batch passes, not a continuous loop

**Status:** proposed (ratifies with RFC-001) · **Date:** 2026-09-05

## Context
The risky operation (scraping LinkedIn on a live personal session) and the
cheap, retryable operations (extract/qualify/draft) have opposite failure
economics. A bug in processing must never require touching LinkedIn again.

## Decision
Two independent passes over a shared SQLite store: `discover` writes raw
posts; `process` consumes them through extract → qualify → draft → Gmail.
No daemon, no scheduler-owned loop; each pass is bounded and human-initiated.

## Consequences
- Reprocessing is free and safe; discovery frequency is a pure risk dial.
- State machine lives in one table (`posts.status`), which doubles as audit log.
- Cost: no real-time reaction to new posts — accepted, freshness window is 24h.
