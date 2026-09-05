"""Discovery: a paced, capped, headed, read-only pass over LinkedIn Posts search.

Runs on YOUR live logged-in session (persistent context in .userdata/), while
you're present and watching. Ctrl-C is the kill switch. Nothing here clicks
Connect, sends messages, or writes anything to LinkedIn.

A pass reports *why* it ended, not just how much it got: stopping on a
LinkedIn interstitial is a safety event that trips the guardrail, while
stopping on our own cap is a job well done. The caller (CLI or skill) needs to
tell those apart.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from urllib.parse import quote

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, sync_playwright

from src.discover import selectors as sel
from src.extract.urls import canonicalize_url
from src.guardrail import Guardrail
from src.models import (
    STOP_CAP_REACHED,
    STOP_LOGIN_WALL,
    STOP_NO_RESULTS,
    STOP_RATE_LIMIT,
    STOP_SEARCHES_EXHAUSTED,
    STOP_SELECTOR_DRIFT,
    STOP_USER_INTERRUPT,
    STOP_WINDOW_ELAPSED,
    WARNING_STOPS,
    DiscoverResult,
    RawPost,
)
from src.store import Store

logger = logging.getLogger("pipeline")

USERDATA_DIR = ".userdata"

SEARCH_URL = (
    "https://www.linkedin.com/search/results/content/"
    "?keywords={keywords}&datePosted=%22past-24h%22&sortBy=%22date_posted%22"
)


class StopRun(Exception):
    """Clean stop. `kind` is a STOP_* constant so callers can branch on it."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def _human_pause(delays: dict) -> None:
    time.sleep(random.uniform(delays["min_seconds"], delays["max_seconds"]))


def _first_match(scope: Page | Locator, candidates: list[str]) -> Locator | None:
    for candidate in candidates:
        loc = scope.locator(candidate)
        if loc.count() > 0:
            return loc.first
    return None


def _check_interstitials(page: Page) -> None:
    for marker in sel.LOGIN_WALL_MARKERS:
        if page.locator(marker).count() > 0:
            raise StopRun(
                STOP_LOGIN_WALL,
                "login wall — session expired; log in manually and retry",
            )
    for marker in sel.RATE_LIMIT_MARKERS:
        if page.locator(marker).count() > 0:
            raise StopRun(
                STOP_RATE_LIMIT,
                "rate-limit / security interstitial — STOP, wait, do not push",
            )
    for marker in sel.NO_RESULTS_MARKERS:
        if page.locator(marker).count() > 0:
            raise StopRun(STOP_NO_RESULTS, "no results for this search")


def _capture_card(card: Locator) -> RawPost | None:
    urn_holder = _first_match(card, sel.URN_HOLDER)
    urn = None
    if urn_holder:
        urn = urn_holder.get_attribute(sel.URN_ATTR) or urn_holder.get_attribute(
            "data-id"
        )
    if not urn:
        urn = card.get_attribute(sel.URN_ATTR)
    if not urn:
        return None  # can't build a stable permalink -> skip, don't guess

    see_more = _first_match(card, sel.SEE_MORE_BUTTON)
    if see_more:
        try:
            see_more.click(timeout=2000)
        except PlaywrightError:
            pass  # truncated text is still usable

    text_loc = _first_match(card, sel.POST_TEXT)
    raw_text = text_loc.inner_text().strip() if text_loc else ""
    if not raw_text:
        return None

    name_loc = _first_match(card, sel.AUTHOR_NAME)
    headline_loc = _first_match(card, sel.AUTHOR_HEADLINE)
    author = (name_loc.inner_text().strip() if name_loc else "unknown")
    if headline_loc:
        author += " — " + headline_loc.inner_text().strip()

    return RawPost(
        url_canonical=canonicalize_url(urn),
        raw_text=raw_text,
        author=author,
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def run_discover(store: Store, keywords: list[str], settings: dict) -> DiscoverResult:
    """One bounded pass over the configured searches."""
    caps = settings["discover"]
    cap = caps["max_posts_per_run"]
    window_s = caps["max_run_minutes"] * 60
    delays = caps["delays"]
    started = time.monotonic()
    deadline = started + window_s
    stored = 0
    searches_run = 0
    stop_kind = STOP_SEARCHES_EXHAUSTED
    stop_detail = "worked through every configured search"

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(USERDATA_DIR, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for search in keywords:
                if stored >= cap:
                    stop_kind, stop_detail = STOP_CAP_REACHED, f"hit the {cap}-post cap"
                    break
                if time.monotonic() > deadline:
                    stop_kind = STOP_WINDOW_ELAPSED
                    stop_detail = f"ran out the {caps['max_run_minutes']}-minute window"
                    break
                logger.info("search: %r", search)
                searches_run += 1
                page.goto(SEARCH_URL.format(keywords=quote(search)))
                page.wait_for_load_state("domcontentloaded")
                _human_pause(delays)
                _check_interstitials(page)

                seen_this_search: set[str] = set()
                idle_scrolls = 0
                while True:
                    if stored >= cap:
                        stop_kind, stop_detail = STOP_CAP_REACHED, f"hit the {cap}-post cap"
                        break
                    if time.monotonic() >= deadline:
                        stop_kind = STOP_WINDOW_ELAPSED
                        stop_detail = f"ran out the {caps['max_run_minutes']}-minute window"
                        break
                    matched = next(
                        (c for c in sel.POST_CARD if page.locator(c).count() > 0), None
                    )
                    if matched is None:
                        _check_interstitials(page)
                        raise StopRun(
                            STOP_SELECTOR_DRIFT,
                            "no post cards matched any selector — LinkedIn layout "
                            "drifted; refresh src/discover/selectors.py via codegen",
                        )
                    card_list = page.locator(matched)
                    new_here = 0
                    for i in range(card_list.count()):
                        if stored >= cap:
                            break
                        try:
                            post = _capture_card(card_list.nth(i))
                        except PlaywrightError as exc:
                            logger.warning("card %d capture failed: %s", i, exc)
                            continue
                        if post is None or post.url_canonical in seen_this_search:
                            continue
                        seen_this_search.add(post.url_canonical)
                        if store.upsert_raw(post):
                            stored += 1
                            new_here += 1
                            logger.info("captured %s", post.url_canonical)
                    idle_scrolls = 0 if new_here else idle_scrolls + 1
                    if idle_scrolls >= caps["max_idle_scrolls"]:
                        logger.info(
                            "no new posts after %d scrolls; next search", idle_scrolls
                        )
                        break
                    page.mouse.wheel(0, random.randint(1200, 2200))
                    _human_pause(delays)
                    _check_interstitials(page)
        except StopRun as exc:
            stop_kind, stop_detail = exc.kind, exc.detail
            logger.warning("run stopped: %s", exc.detail)
        except KeyboardInterrupt:
            stop_kind, stop_detail = STOP_USER_INTERRUPT, "kill switch (Ctrl-C)"
            logger.warning("kill switch (Ctrl-C) — stopping")
        finally:
            context.close()

    warning_recorded = False
    if stop_kind in WARNING_STOPS:
        # PRD §8: a LinkedIn warning pauses discovery and halves the cap. Record
        # it now so the next run is blocked even if this process dies here.
        Guardrail().record_warning(stop_kind, stop_detail)
        warning_recorded = True
        logger.error(
            "LINKEDIN WARNING RECORDED (%s). Discovery is now paused — do not push.",
            stop_kind,
        )

    result = DiscoverResult(
        stored=stored,
        cap=cap,
        searches_run=searches_run,
        searches_total=len(keywords),
        stop_reason=stop_kind,
        stop_detail=stop_detail,
        duration_seconds=round(time.monotonic() - started, 1),
        warning_recorded=warning_recorded,
    )
    logger.info(
        "discover done: %d new posts stored (%s)", result.stored, result.stop_reason
    )
    return result
