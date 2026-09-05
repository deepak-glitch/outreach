# outreach — job-post pipeline (v1)

A local, human-paced tool that reads LinkedIn **Posts** search for recruiter/hiring
posts, extracts structured job data, qualifies against your rules, and — for posts
with an email contact — drafts a resume-grounded outreach email into your **Gmail
Drafts** for you to review and send by hand.

**Non-goals (v2 backlog):** auto-connect / auto-message on LinkedIn · auto-send
email · always-on daemon · cloud hosting · RAG.

**Deployment reality:** runs on *your* machine, headed, on *your* logged-in
LinkedIn session, in bounded passes while you're present. Not a cloud service.

## Architecture

```
[discover]  Playwright → paced Posts scrape → raw posts into SQLite
   ↓  (separate run)
[process]   extract → qualify (code filters → LLM) → draft → Gmail draft
   ↓
[review]    you read drafts in Gmail, send the good ones by hand
```

Staged means the risky LinkedIn scrape is decoupled from everything downstream:
a bug in extract/qualify/draft re-runs against stored posts without touching
LinkedIn again.

## Setup

### 1. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Google Cloud / Gmail

1. Create a Google Cloud project, enable the **Gmail API**.
2. OAuth consent screen: External, Testing mode, add yourself as a test user.
3. Create a **Desktop app** OAuth client and download `credentials.json` to
   `.secrets/credentials.json`.
4. Scope used is `gmail.compose` only — the tool can create drafts but never
   read your inbox and never send.

First `process` run without `--dry-run` opens a browser for OAuth once; the
refresh token persists to `.secrets/token.json`.

### 3. LLM key

Set `ANTHROPIC_API_KEY` in your shell, or put the key in `.secrets/llm_key`.
Models are configured in `config/settings.json` (a cheap model for
classify/qualify, a stronger one for drafting).

### 4. Your data

- `config/resume.txt` — plain text, the **only** experience the drafter may use.
  Copy `config/resume.example.txt` and fill it in.
- `config/resume.pdf` — the attachment sent to recruiters.
- `config/rules.json` — your hard filters: work-auth phrasing that disqualifies,
  allowed employment types, location/remote requirements, and the
  `target_role_description` the relevance LLM screens against.
- `config/keywords.json` — the Posts searches to run.

### 5. LinkedIn session + selectors

First `discover` run opens a headed Chromium on a fresh profile in `.userdata/`
— log in by hand once; the session persists. **`.userdata/` is a credential:
gitignored, never committed, never copied off this machine.**

Selectors in `src/discover/selectors.py` rot as LinkedIn ships UI changes.
When discover fails loud ("no post cards matched any selector"), refresh them:

```bash
playwright codegen "https://www.linkedin.com/search/results/content/?keywords=ai%20engineer"
```

Log in, set *Posts* + *Past 24 hours*, scroll, harvest locators — then throw
the generated script away and update `selectors.py` only.

## Running

```bash
python run.py preflight                # verify setup before a run
python run.py discover                 # one paced, capped, headed pass
python run.py process --dry-run        # extract → qualify → draft (printed, no Gmail)
python run.py process                  # same, but real drafts land in Gmail Drafts
python run.py status                   # post counts by pipeline status
python run.py guardrail                # account-safety state
```

Useful flags: `discover --cap 10`, `process --stage extract --stage qualify`.
Every subcommand takes `--json` for machine-readable output — that is how the
skills layer reads results.

### Talking to it instead

`skills/` holds SKILL.md skills that Claude Code discovers automatically, so
the pipeline can be driven conversationally ("find fresh hiring posts") rather
than by remembering flags. The skills call this same CLI; nothing is bypassed.

### Account guardrail

The PRD's stop conditions are enforced in code, not left to memory. One
LinkedIn warning pauses discovery for 48h and halves the recommended cap; a
second stops it until a person reviews pacing. State lives in
`data/guardrail.json`. Clear it deliberately, after actually changing
something:

```bash
python run.py guardrail --clear "lengthened delays, halved cap"
```

### Tests

```bash
python -m pytest tests/ -q
```

Everything tunable (caps, delays, run window, models) lives in
`config/settings.json`. Logs land in `logs/`, one file per run. The DB is
`data/pipeline.db`; the `posts` table is the dedup key, audit trail, and status
machine (`captured → extracted → qualified → drafted`, with `skipped`/`error`).

Posts whose contact is a DM or link (not email) are stored as **v2 candidates**
with full extracted data — v2 never has to re-scrape them.

## Risk controls (non-negotiable)

- `.userdata/` and `.secrets/` gitignored — never committed.
- Discovery: headed, paced, capped, bounded window, run while present. Ctrl-C
  is the kill switch.
- No auto-send. Human gate = Gmail Drafts. Every send is your click.
- Hard filters (work-auth etc.) are code, logged, auditable — not LLM vibes.
- The drafter sees only your resume — structural anti-hallucination; drafts
  claiming skills the resume lacks are flagged in the log.
- One post's failure never kills the batch (`status=error`, run continues).
- LinkedIn warning → stop, wait, don't push. See `RUNBOOK.md`.
