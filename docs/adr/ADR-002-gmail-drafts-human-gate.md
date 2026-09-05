# ADR-002: Gmail Drafts is the human gate; gmail.compose scope only

**Status:** proposed (ratifies with RFC-001) · **Date:** 2026-09-05

## Context
Outbound email reputation is unrecoverable, and recruiters are the audience
that decides interviews. Full automation of sends was rejected at kickoff.

## Decision
The pipeline's terminal write is `drafts.create` with `resume.pdf` attached,
under the `https://www.googleapis.com/auth/gmail.compose` scope exclusively.
Every send is a human click inside Gmail. No inbox read access in v1.

## Consequences
- The review queue is a product Deepak already uses daily — zero new UI.
- The tool cannot read replies (reply tracking is v2 and will require a scope
  change reviewed on its own).
- A compromised or buggy run can at worst fill Drafts, never send.
