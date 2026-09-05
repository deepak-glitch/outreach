# Discovery troubleshooting

Read this when a pass fails in a way the `stop_reason` table in SKILL.md does
not resolve.

## Selector drift (`stop_reason: selector_drift`)

**What it means:** the page loaded, but nothing on it matched any of the CSS
selectors in `src/discover/selectors.py`. LinkedIn ships UI changes regularly,
so this is expected maintenance, not a bug or a ban signal.

**Why it fails loud instead of continuing:** a scraper that keeps going after
its selectors stop matching silently produces garbage — empty posts, wrong
authors, posts attributed to the wrong URL. Bad data in the store is worse
than no data, because it flows all the way to a draft email addressed to the
wrong person. Stopping is correct.

**The fix** is to harvest fresh locators by hand. This needs a person at the
browser:

```bash
playwright codegen "https://www.linkedin.com/search/results/content/?keywords=ai%20engineer"
```

Log in, set the filters to **Posts** and **Past 24 hours**, scroll a little,
and watch what codegen emits as it records. Then update
`src/discover/selectors.py` — and only that file, which exists precisely so
drift is a one-file fix.

Two things worth knowing when you do:

- Throw the generated script away. It is a recording, not a design; we want
  the locators out of it, nothing else.
- Prefer role- and attribute-based locators over the long CSS chains codegen
  emits by default. Chains like `div > div:nth-child(3) > span` break on the
  next redesign; something anchored to `data-urn` or a role survives longer.

Each entry in `selectors.py` is an ordered fallback list — the first selector
that matches wins. When you find a new one, add it at the top rather than
replacing the old one, so the file keeps working across a gradual rollout
where some sessions see the new UI and some the old.

## Login wall (`stop_reason: login_wall`)

The saved session expired or was invalidated. This trips the guardrail,
because a session dying mid-pass can indicate LinkedIn ended it deliberately
rather than it simply aging out.

Recovery is a manual login on the next run — the browser opens, the user signs
in, and the session persists again. If the wall appears immediately on every
run, the stored profile is broken and needs resetting:

```bash
rm -rf .userdata/
python run.py discover    # log in by hand when the browser opens
```

Treat `.userdata/` as a credential. It holds a live authenticated session; it
is gitignored, and it should never be copied off the machine or shared.

## Rate limit / security interstitial (`stop_reason: rate_limit_warning`)

LinkedIn showed a security check, an unusual-activity notice, or a limit
screen. The engine records the warning and pauses discovery.

The correct response is to wait — 48 hours, per the guardrail — and resume at
the halved cap it recommends. Not a smaller run, not a different account, not
a VPN. This is the signal the whole pacing design exists to respect, and the
account is worth more than the week of outreach.

If a second warning follows the first, discovery stops until pacing is
reviewed. That review is a real one: lengthen the delays in
`config/settings.json`, cut the cap, or run less often.

## Nothing captured, but no error

A pass that ends `searches_exhausted` with `stored: 0` usually means one of:

- **Every post was already stored.** Dedup is by canonical post URL, so
  re-running soon after a pass legitimately finds nothing new. Check
  `python run.py status --json` — if the store has posts, this is the answer.
- **The searches are too narrow.** Recruiter phrasing varies more than people
  expect. Broadening the queries in `config/keywords.json` is the fix.
- **Wrong time of day.** The `Past 24 hours` filter means an early-morning run
  sees a thin overnight window.

## Where to look

- `logs/discover-<timestamp>.log` — one file per run: every search tried, every
  post captured with its URL, every card that failed to parse, and the stop
  reason with detail.
- `data/pipeline.db`, table `posts` — the system of record. `status='captured'`
  are posts waiting for `process`.
- `data/guardrail.json` — warning history and the current cooldown. Plain JSON
  on purpose: getting past a block means a person opening it and deciding.
