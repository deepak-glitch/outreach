# RFC-001 — Architecture: skill-driven outreach pipeline

**Status:** in review · **Author:** Claude (tech lead) · **Approver:** Deepak (PO)
**Inputs:** PRD v0.2 · spike code on this branch · reference product
[sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills)

## 1. Summary

Three-layer system. A **skills layer** (SKILL.md folders, auto-discovered by
Claude Code) is the primary interface: Deepak talks to Claude, Claude runs the
right stage and narrates results. Underneath, the existing **deterministic
Python engine** (discover/extract/qualify/draft/gmail/store) does the actual
work — skills never free-hand a scrape or an email; they call the engine.
State lives in **SQLite + Gmail Drafts + config files**, same as the spike.

## 2. What we learned from the reference repo

sergebulaev/linkedin-skills validates three patterns we adopt:

1. **SKILL.md as the product surface.** Each capability is a folder with
   frontmatter + instructions; the agent auto-triggers it from natural
   language. Their `lib/` + `scripts/` split shows skills should delegate to
   plain, testable Python — instructions orchestrate, code executes.
2. **Human approval before anything leaves the machine** — identical to our
   Gmail-drafts gate; their skills draft and wait.
3. **Third-party read APIs (Apify) as an alternative to scraping yourself.**
   Considered below (§6) — not chosen for v1, kept as the designed escape
   hatch if account risk materializes.

Where we differ: their domain is content marketing (posting, comments,
engagement); ours is inbound job outreach. We take the *form factor*, not the
skill list.

## 3. Whiteboard

```
┌──────────────────────────── Claude Code session ────────────────────────────┐
│  "find fresh posts"      "process them"       "why rejected?"   "review"    │
│        │                      │                     │               │       │
│  ┌─────▼──────┐  ┌───────────▼──────────┐  ┌───────▼──────┐  ┌─────▼─────┐ │
│  │ outreach-  │  │ outreach-process     │  │ outreach-    │  │ outreach- │ │
│  │ discover   │  │ (dry-run first, show │  │ status       │  │ review    │ │
│  │ SKILL.md   │  │  drafts, then real)  │  │ /explain     │  │ drafts    │ │
│  └─────┬──────┘  └───────────┬──────────┘  └───────┬──────┘  └─────┬─────┘ │
└────────┼─────────────────────┼─────────────────────┼───────────────┼───────┘
         │ invokes             │ invokes             │ reads         │ reads
┌────────▼─────────────────────▼─────────────────────▼───────────────▼───────┐
│                    Python engine (src/ + run.py, unchanged role)           │
│  discover ──▶ store ──▶ extract ──▶ qualify ──▶ draft ──▶ gmail            │
│  Playwright   SQLite    LLM+regex   rules→LLM   resume     drafts.create   │
└────────┬───────────┬──────────────────────────────────────────┬───────────┘
         │           │                                          │
   ┌─────▼────┐ ┌────▼──────────┐                        ┌──────▼─────┐
   │.userdata/│ │data/pipeline.db│                        │Gmail Drafts│
   │(session) │ │(system of     │                        │(human gate)│
   └──────────┘ │ record)       │                        └────────────┘
                └───────────────┘
```

Trust boundaries: `.userdata/` and `.secrets/` never cross up into skill
output; skills read the DB and logs, never credentials.

## 4. Skills catalog (v1)

| Skill | Trigger examples | Delegates to | Human gate |
|---|---|---|---|
| `outreach-discover` | "find fresh hiring posts", "run discovery" | `run.py discover` (headed; user must be present — skill checks and says so) | user watches the browser |
| `outreach-process` | "process the pipeline", "make drafts" | `run.py process --dry-run` first; presents drafts in-chat; only on explicit OK runs real `process` | approve before drafts.create; sends stay manual in Gmail |
| `outreach-review` | "review my drafts", "make this sound more human" | reads DB + draft text; critiques against resume.txt (off-resume claims, tone); edits go back through the engine | user sends from Gmail |
| `outreach-status` | "pipeline status", "why was X rejected" | `run.py status` + SQL over `posts` (verdict_reason audit trail) | read-only |
| `outreach-tune` | "never show me contract roles", "add a search for agentic AI" | edits `rules.json` / `keywords.json` / `settings.json`, shows diff, re-runs qualify on stored posts to preview effect | user confirms diff |

v2 candidates (parked, mirrors reference repo's engagement tooling): reply
tracking, DM-branch handling, multi-resume selection.

## 5. Design decisions (each gets an ADR)

- **ADR-001** Staged batch passes, not a continuous loop.
- **ADR-002** Gmail Drafts is the human gate; `gmail.compose` scope only.
- **ADR-003** Hard filters in code before any LLM verdict.
- **ADR-004** Skills layer wraps a deterministic engine (this RFC's core).
- **ADR-005** Own-session Playwright for read-side; Apify-style API is the
  documented fallback, not the default.

## 6. Alternatives considered

| Alternative | Why not (v1) |
|---|---|
| Skills-only, no engine (Claude free-hands each step) | Non-reproducible, unauditable, every run costs full LLM reasoning; violates F5 auditability |
| CLI-only, no skills (spike as-is) | Rejected by PO — conversational operation is now G5/F12 |
| Apify actors for read-side (reference repo's approach) | $ per read, still ToS-adjacent, adds a third party holding our query patterns. **But**: zero own-account risk. Escape hatch: if guardrail trips twice (PRD §8), we revisit with an `ApifySource` behind the same `RawPost` contract |
| Publora-style publishing API | Publishes *posts*; we send *emails*. Not our funnel |
| MCP server instead of skills | Heavier to build/maintain for one user; skills are files in the repo, reviewable in PRs like everything else |

## 7. Impact on the spike

The engine survives largely as-is (it was built to the same contracts). Gaps
the skills layer exposes, to become tickets in Stage 4:

1. `skills/` directory + 5 SKILL.md files (new).
2. Engine needs machine-readable output for skills: `run.py` gets `--json`
   on `status`/`process` summaries (small change).
3. `outreach-tune` needs a "re-qualify stored posts" entry point (new
   `process --stage qualify --requeue` or similar).
4. Draft text must be readable pre-Gmail for `outreach-review` → persist
   draft subject/body in DB, not only in Gmail (schema: add `draft_subject`,
   `draft_body`).
5. Tests: the engine has none beyond session smoke tests — unit tests become
   first-class tickets.

## 8. Rollout

Skills land one PR each (Stage 5), engine changes first. No behavior change
for CLI users at any point; skills are additive.

## Sign-off

- [ ] PO approves RFC → ADRs are ratified → Stage 4 (sprint planning)
