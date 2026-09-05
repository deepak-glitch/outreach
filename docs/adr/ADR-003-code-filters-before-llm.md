# ADR-003: Hard filters in code before any LLM verdict

**Status:** proposed (ratifies with RFC-001) · **Date:** 2026-09-05

## Context
Some rejections are non-negotiable facts about the user (work authorization,
employment type, location). LLM judgments are probabilistic and unauditable;
these rules must be neither.

## Decision
`rules.json` phrase/field filters run first, in plain Python, and each
rejection writes a literal, quotable `verdict_reason` (`[rules] work-auth:
post says 'no sponsorship'`). Only survivors spend LLM tokens on the
relevance screen, whose verdicts are tagged `[llm]`.

## Consequences
- Deterministic, testable, explainable rejections; cheaper qualify stage.
- Phrase lists need maintenance as recruiter wording drifts — the
  `outreach-tune` skill (RFC-001 §4) is the maintenance interface.
