# ADR-004: Skills layer wraps a deterministic engine

**Status:** proposed (ratifies with RFC-001) · **Date:** 2026-09-05

## Context
PO direction (PRD v0.2, G5/F12): operate the pipeline conversationally from
Claude Code, in the style of sergebulaev/linkedin-skills. The alternative
extremes — skills that free-hand each step with no engine, or CLI-only with
no skills — fail auditability and the PO requirement respectively.

## Decision
Capabilities ship as `skills/<name>/SKILL.md` folders (agentskills.io
convention: frontmatter + instructions, auto-discovered by Claude Code).
Skill instructions orchestrate and narrate; all scraping, filtering,
drafting, and Gmail writes go through the Python engine (`run.py` / `src/`).
Skills may read the DB/logs/config; they never touch `.userdata/` or
`.secrets/`, and never generate an email outside the engine's resume-grounded
draft path.

## Consequences
- Two surfaces, one engine: CLI stays fully functional; skills are additive.
- Engine grows machine-readable outputs (`--json`) and persisted draft text
  so skills can present results without re-deriving them.
- Skill docs become part of code review — behavior changes to instructions
  go through PRs like code.
