# RUNBOOK

## Start a pass

```bash
source .venv/bin/activate
python run.py discover            # sit with it — it's headed on your live session
python run.py process --dry-run   # audit the drafts in the log first
python run.py process             # real drafts.create into Gmail Drafts
```

Ramp `discover.max_posts_per_run` in `config/settings.json` slowly, only while
LinkedIn stays quiet. Start ~25.

## Where things land

| Thing | Where |
|---|---|
| Drafts to review | Gmail → Drafts (recipient, subject, body, resume.pdf attached) |
| Pipeline state | `data/pipeline.db`, table `posts` |
| Per-run logs | `logs/<stage>-<timestamp>.log` |
| v2 candidates (DM/link contact) | `posts` rows with `status=skipped`, reason "v2 candidate" |

## Read the DB

```bash
sqlite3 data/pipeline.db "SELECT status, COUNT(*) FROM posts GROUP BY status;"
sqlite3 data/pipeline.db "SELECT url_canonical, verdict_reason FROM posts WHERE status='skipped';"
sqlite3 data/pipeline.db "SELECT url_canonical FROM posts WHERE low_confidence=1;"
```

`low_confidence=1` rows are held at `extracted` for manual review: inspect the
post, fix `contact_email` if needed, then clear the flag to let qualify pick it up:

```bash
sqlite3 data/pipeline.db "UPDATE posts SET low_confidence=0 WHERE url_canonical='...';"
```

Re-process a post from scratch: set `status='captured'` and clear derived fields.

## Kill switch

Ctrl-C, any stage, any time. The DB commits per post, so state stays consistent;
re-running is idempotent (dedup by canonical URL, stages only pick up their
input status).

## LinkedIn shows a warning / security check / unusual-activity page

**Stop. Wait (a day, not an hour). Don't push.** The account runs your live
interviews; it's the asset. When you come back, halve the cap and lengthen the
delays in `config/settings.json`. Repeated warnings → stop using discover until
you've rethought pacing.

## Gmail token problems

- `GmailAuthError: token refresh failed` → `rm .secrets/token.json`, re-run
  `python run.py process`; OAuth opens in the browser once.
- Consent screen in Testing mode expires refresh tokens after ~7 days of
  disuse — same fix.
- Never share or commit `.secrets/`.

## LinkedIn session broken (login wall every run)

```bash
rm -rf .userdata/
python run.py discover   # log in by hand once when the browser opens
```

## Selector drift ("no post cards matched any selector")

LinkedIn changed the DOM. `playwright codegen` the Posts search URL, harvest
fresh locators, update `src/discover/selectors.py` only. Fail-loud is by
design — never scrape garbage silently.

## Scheduling (optional, bounded, present)

Fully manual is fine. If you want a nudge, a `cron`/`launchd` entry may fire a
*single capped pass* at a time you're at the machine — **not** a daemon, **not**
unattended. Example (macOS, weekdays 9:30am — you're at your desk):

```
30 9 * * 1-5 cd /path/to/outreach && .venv/bin/python run.py discover >> logs/cron.log 2>&1
```

`process` you run by hand after auditing the discover log.
