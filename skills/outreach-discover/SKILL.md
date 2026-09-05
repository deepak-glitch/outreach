---
name: outreach-discover
description: Run a safe, capped LinkedIn Posts discovery pass for the job-outreach pipeline — finds fresh recruiter/hiring posts and stores them in SQLite for later processing. Use this whenever the user wants to find new job posts, run discovery, check LinkedIn for hiring posts, pull fresh leads into the pipeline, or asks something like "anything new today?" about their job search. Also use it when they ask whether it is safe to run discovery, why discovery is blocked, or want to clear a LinkedIn warning — this skill owns the account-safety guardrail and is the only correct way to start a scrape.
---

# Discover: fresh hiring posts, without risking the account

This skill runs one bounded pass over LinkedIn Posts search on the user's own
logged-in session, and stores raw posts for the `process` stage to work on
later.

The thing to understand before anything else: **the LinkedIn account is the
asset this whole project exists to protect.** It runs the user's live
interviews. A restricted account costs far more than a slow week of outreach.
Everything below is shaped by that, and the engine enforces it in code so the
rules survive a tired 11pm run.

## The one rule

**Never start a discovery pass the user is not present for.** The browser is
headed and runs on their real session; they are the kill switch (Ctrl-C) and
the thing that notices a warning screen the selectors miss. If there is any
signal they are stepping away, are on a phone, or want this scheduled or run
in the background, say plainly that discovery does not work that way and offer
`outreach-process` instead — processing stored posts is completely safe,
touches no LinkedIn surface, and is usually the more useful thing anyway.

## How to run a pass

Work from the repo root. Every command takes `--json`; use it and parse the
result rather than reading the human-formatted text, which is meant for the
user's eyes and will change.

### 1. Preflight

```bash
python run.py preflight --json
```

Read `ok_for_discover`. If it is false, the `checks` array names exactly what
blocks it and a `fix` for each — relay those and stop. Common ones:

- `playwright` / `chromium` failing → the user needs `pip install -r
  requirements.txt` and `playwright install chromium`.
- `account guardrail` failing → a LinkedIn warning is on record. Jump to
  **When the guardrail blocks you** below; do not try to work around it.
- `linkedin session` warning (not a failure) → this is a first run. Tell the
  user a browser will open and they log in by hand once; the session persists
  after that.

A `resume` warning does not block discovery — mention it only if they are
likely to run `process` right after.

### 2. Confirm they are at the machine

Ask before launching if you do not already know. A real answer matters here;
"probably" is a no. Frame it as what it is — you are about to open a browser
on their live LinkedIn account and they need to be watching it.

### 3. Run

```bash
python run.py discover --json
```

Add `--cap N` if the user asks for a smaller pass or the guardrail recommended
a reduced cap. Do not raise the cap above what `config/settings.json` sets on
your own initiative — that number is the project's risk dial and changing it
is the user's call, made deliberately.

This blocks for minutes by design: the pacing between actions is jittered and
human-scale. That slowness is the safety feature, not a bug to route around.

### 4. Read the outcome, not just the count

The result's `stop_reason` matters more than `stored`. A pass that captured 3
posts and stopped clean is fine; a pass that captured 20 and hit an
interstitial is a problem.

| `stop_reason` | What happened | What to tell the user |
|---|---|---|
| `cap_reached` | Hit the configured post cap | Normal, healthy. Suggest running `process` next. |
| `window_elapsed` | Ran out the time window | Normal. Fewer posts than the cap; fine. |
| `searches_exhausted` | Worked through every search | Normal. If `stored` is 0, the searches may be too narrow — offer `outreach-tune`. |
| `user_interrupt` | They hit Ctrl-C | Whatever was captured is saved. No action needed. |
| `no_results` | LinkedIn returned nothing | Usually a too-narrow query or an odd time of day. Suggest revisiting keywords. |
| `selector_drift` | No post cards matched any selector | LinkedIn changed its DOM. **This is not a scrape failure to retry** — see `references/troubleshooting.md`. |
| `login_wall` | Session expired mid-pass | Guardrail tripped. See below. |
| `rate_limit_warning` | LinkedIn showed a security/limit screen | **Guardrail tripped. Stop.** See below. |

If `warning_recorded` is true, the engine has already paused discovery. Say so
clearly and do not offer to retry — retrying after a warning is the single
worst thing to do here, and the exit code (3) reflects that the run was not a
success even if posts were stored.

### 5. Report back

Give the user: how many new posts landed, why the pass ended, and one concrete
next step. Keep it short — they can read the log file if they want detail.
When the pass went normally and posts were stored, the natural next step is
processing them into drafts.

## When the guardrail blocks you

The guardrail implements the stop conditions agreed in the PRD: one LinkedIn
warning pauses discovery for 48 hours and halves the recommended cap; a second
warning stops discovery until a person reviews pacing.

```bash
python run.py guardrail --json
```

`verdict` is `cooldown` (wait it out) or `review_required` (needs a human
decision). Report the reason and `resume_at` plainly.

**Do not offer workarounds.** Not a smaller cap, not a different search, not
"just one quick run". The user can clear it themselves with `python run.py
guardrail --clear "what I changed"`, and that is deliberately a thing they type
rather than something you do for them — clearing it is an accountable decision
about their own account, and the friction is the point. If they ask you to
clear it, explain what clearing means and let them run the command.

Processing already-stored posts stays available the whole time the guardrail
is up. Offer that instead; it is genuinely productive work that carries none
of the risk.

## Further reading

- `references/troubleshooting.md` — selector drift and how to refresh the
  locators, session resets, first-run login, and what the log files contain.
  Read it when a run fails in a way the table above does not resolve.
