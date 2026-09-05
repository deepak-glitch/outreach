#!/usr/bin/env python3
"""CLI entry point.

    python run.py discover [--cap N] [--keywords FILE]
    python run.py process  [--dry-run] [--stage extract|qualify|draft ...]
    python run.py status

discover does one bounded, headed, paced pass over LinkedIn Posts search.
process runs the stored posts through extract -> qualify -> draft -> Gmail.
Ctrl-C is the kill switch everywhere.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.log import setup_logging
from src.settings import load_keywords, load_settings
from src.store import Store


def cmd_discover(args) -> int:
    from src.discover import run_discover  # import here: playwright not needed for process

    logger = setup_logging("discover")
    settings = load_settings()
    if args.cap:
        settings["discover"]["max_posts_per_run"] = args.cap
    keywords = load_keywords(Path(args.keywords) if args.keywords else None)
    with Store() as store:
        run_discover(store, keywords, settings)
    return 0


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
    return 0


def cmd_status(args) -> int:
    with Store() as store:
        counts = store.counts_by_status()
    if not counts:
        print("empty database — run `python run.py discover` first")
        return 0
    for status, n in sorted(counts.items()):
        print(f"{status:>10}  {n}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LinkedIn job-post outreach pipeline (v1)")
    sub = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
