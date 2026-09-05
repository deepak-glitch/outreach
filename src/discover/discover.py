"""Discovery: a paced, capped, headed, read-only pass over LinkedIn Posts search.

Runs on YOUR live logged-in session (persistent context in .userdata/), while
you're present and watching. Ctrl-C is the kill switch. Nothing here clicks
Connect, sends messages, or writes anything to LinkedIn.
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
from src.models import RawPost
from src.store import Store

logger = logging.getLogger("pipeline")

USERDATA_DIR = ".userdata"

SEARCH_URL = (
    "https://www.linkedin.com/search/results/content/"
    "?keywords={keywords}&datePosted=%22past-24h%22&sortBy=%22date_posted%22"
)


class StopRun(Exception):
    """Clean stop: interstitial, login wall, or run window exhausted."""


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
            raise StopRun("login wall — session expired; log in manually and retry")
    for marker in sel.RATE_LIMIT_MARKERS:
        if page.locator(marker).count() > 0:
            raise StopRun(
                "rate-limit / security interstitial — STOP, wait, do not push"
            )
    for marker in sel.NO_RESULTS_MARKERS:
        if page.locator(marker).count() > 0:
            raise StopRun("no results for this search")


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


def run_discover(store: Store, keywords: list[str], settings: dict) -> int:
    """One bounded pass. Returns the number of new posts stored."""
    caps = settings["discover"]
    cap = caps["max_posts_per_run"]
    window_s = caps["max_run_minutes"] * 60
    delays = caps["delays"]
    deadline = time.monotonic() + window_s
    stored = 0

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            USERDATA_DIR, headless=False
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for search in keywords:
                if stored >= cap or time.monotonic() > deadline:
                    break
                logger.info("search: %r", search)
                page.goto(SEARCH_URL.format(keywords=quote(search)))
                page.wait_for_load_state("domcontentloaded")
                _human_pause(delays)
                _check_interstitials(page)

                seen_this_search: set[str] = set()
                idle_scrolls = 0
                while stored < cap and time.monotonic() < deadline:
                    cards = _first_match(page, sel.POST_CARD)
                    if cards is None:
                        _check_interstitials(page)
                        raise StopRun(
                            "no post cards matched any selector — LinkedIn layout "
                            "drifted; refresh src/discover/selectors.py via codegen"
                        )
                    card_list = page.locator(
                        next(c for c in sel.POST_CARD if page.locator(c).count() > 0)
                    )
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
                        logger.info("no new posts after %d scrolls; next search", idle_scrolls)
                        break
                    page.mouse.wheel(0, random.randint(1200, 2200))
                    _human_pause(delays)
                    _check_interstitials(page)
        except StopRun as exc:
            logger.warning("run stopped cleanly: %s", exc)
        except KeyboardInterrupt:
            logger.warning("kill switch (Ctrl-C) — stopping")
        finally:
            context.close()

    logger.info("discover done: %d new posts stored", stored)
    return stored
