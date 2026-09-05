#!/usr/bin/env python3
"""CLI entry point.

    python run.py preflight [--json]        check setup before a run
    python run.py discover [--cap N] [--json] [--keywords FILE]
    python run.py process  [--dry-run] [--stage extract|qualify|draft]
    python run.py status [--json]
    python run.py guardrail [--clear "note"] [--json]

discover does one bounded, headed, paced pass over LinkedIn Posts search.
process runs the stored posts through extract -> qualify -> draft -> Gmail.
Ctrl-C is the kill switch everywhere.

Every subcommand takes --json so the skills layer can read results instead of
scraping human-formatted text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.log import setup_logging
from src.settings import load_keywords, load_settings
from src.store import Store

STATUS_ICON = {"pass": "✓", "warn": "!", "fail": "✗"}


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))


def cmd_preflight(args) -> int:
    from src.preflight import run_preflight

    settings = load_settings() if Path("config/settings.json").exists() else {}
    base_cap = settings.get("discover", {}).get("max_posts_per_run")
    report = run_preflight(base_cap)

    if args.json:
        _emit(report.to_dict(), True)
    else:
        for check in report.checks:
            print(f"  {STATUS_ICON[check.status]} {check.name}: {check.detail}")
            if check.fix and check.status != "pass":
                print(f"      → {check.fix}")
        print()
        print(f"discover: {'ready' if report.ok_for('discover') else 'BLOCKED'}")
        print(f"process:  {'ready' if report.ok_for('process') else 'BLOCKED'}")
    return 0 if report.ok_for("discover") else 1


def cmd_discover(args) -> int:
    # Import preflight only at first: src.discover pulls in playwright, and a
    # missing browser dependency should surface as a readable blocker rather
    # than an ImportError traceback.
    from src.preflight import run_preflight

    logger = setup_logging("discover")
    settings = load_settings()
    if args.cap:
        settings["discover"]["max_posts_per_run"] = args.cap

    # Preflight is not optional: discovery opens a browser on the live account,
    # and the guardrail check lives here. Failing fast beats a half-run.
    report = run_preflight(settings["discover"]["max_posts_per_run"])
    if not report.ok_for("discover"):
        blockers = [{"name": c.name, "detail": c.detail, "fix": c.fix}
                    for c in report.blocks("discover")]
        for blocker in blockers:
            logger.error("BLOCKED — %s: %s", blocker["name"], blocker["detail"])
        _emit({"ok": False, "blocked": True, "blockers": blockers}, args.json)
        return 2

    from src.discover import run_discover

    keywords = load_keywords(Path(args.keywords) if args.keywords else None)
    with Store() as store:
        result = run_discover(store, keywords, settings)
        counts = store.counts_by_status()

    payload = {"ok": True, "blocked": False, **result.to_dict(), "status_counts": counts}
    _emit(payload, args.json)
    # A run that tripped the guardrail is not a success, even if it stored posts.
    return 3 if result.warning_recorded else 0


def cmd_process(args) -> int:
    from src.process import run_process

    logger = setup_logging("process")
    settings = load_settings()
    stages = args.stage or ["extract", "qualify", "draft"]
    with Store() as store:
        try:
            run_process(store, settings, dry_run=args.dry_run, stages=stages)
        except KeyboardInterrupt:
            logger.warning("kill switch (Ctrl-C) — stopping; DB state is consistent")
            return 130
        _emit({"ok": True, "status_counts": store.counts_by_status()}, args.json)
    return 0


def cmd_status(args) -> int:
    with Store() as store:
        counts = store.counts_by_status()
    if args.json:
        _emit({"status_counts": counts}, True)
        return 0
    if not counts:
        print("empty database — run `python run.py discover` first")
        return 0
    for status, n in sorted(counts.items()):
        print(f"{status:>10}  {n}")
    return 0


def cmd_guardrail(args) -> int:
    from src.guardrail import Guardrail

    rail = Guardrail()
    if args.clear is not None:
        rail.clear(args.clear)
        print(f"guardrail cleared: {args.clear or '(no note)'}")
        return 0
    settings = load_settings() if Path("config/settings.json").exists() else {}
    decision = rail.check(settings.get("discover", {}).get("max_posts_per_run"))
    if args.json:
        _emit(decision.to_dict(), True)
    else:
        print(f"{decision.verdict}: {decision.reason}")
        if decision.recommended_cap:
            print(f"recommended cap on resume: {decision.recommended_cap}")
    return 0 if decision.allowed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="LinkedIn job-post outreach pipeline (v1)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pre = sub.add_parser("preflight", help="verify setup before a run")
    p_pre.set_defaults(fn=cmd_preflight)

    p_discover = sub.add_parser("discover", help="paced, capped LinkedIn Posts scrape")
    p_discover.add_argument("--cap", type=int, help="override max posts this run")
    p_discover.add_argument("--keywords", help="alternate keywords JSON file")
    p_discover.set_defaults(fn=cmd_discover)

    p_process = sub.add_parser("process", help="extract -> qualify -> draft -> Gmail")
    p_process.add_argument("--dry-run", action="store_true",
                           help="do everything except drafts.create (print drafts)")
    p_process.add_argument("--stage", action="append",
                           choices=["extract", "qualify", "draft"],
                           help="run only these stages (repeatable); default: all")
    p_process.set_defaults(fn=cmd_process)

    p_status = sub.add_parser("status", help="post counts by pipeline status")
    p_status.set_defaults(fn=cmd_status)

    p_rail = sub.add_parser("guardrail", help="account-safety state (PRD §8)")
    p_rail.add_argument("--clear", nargs="?", const="", metavar="NOTE",
                        help="clear warnings after reviewing pacing")
    p_rail.set_defaults(fn=cmd_guardrail)

    for p in (p_pre, p_discover, p_process, p_status, p_rail):
        p.add_argument("--json", action="store_true", help="machine-readable output")

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
