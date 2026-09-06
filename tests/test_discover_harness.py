"""End-to-end proof that the capture loop works.

Everything else we can test is control logic — guardrails, gating, contracts.
This is the part that actually reads a page, and until it ran against a real
DOM it was the biggest unproven claim in the project. The fixture reproduces
LinkedIn's shapes rather than LinkedIn itself, so this makes no network
request and needs nobody supervising it; what it proves is that our selectors,
card capture, deduplication, cap and stop-reason logic hold up against markup
that behaves like the real thing.
"""

import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

from src.models import STOP_CAP_REACHED, STOP_SEARCHES_EXHAUSTED
from src.store import Store

playwright = pytest.importorskip("playwright.sync_api")

FIXTURES = Path(__file__).parent / "fixtures"

# The container ships a chromium the pip package's version pin doesn't match,
# so point at the binary directly when it's there and skip when it isn't.
CHROMIUM = next(
    (p for p in ("/opt/pw-browsers/chromium",) if Path(p).exists()),
    shutil.which("chromium") or shutil.which("chromium-browser"),
)


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def env(fixture_server, tmp_path):
    from src.discover import DiscoverEnv

    if not CHROMIUM:
        pytest.skip("no chromium binary available")
    return DiscoverEnv(
        search_url=fixture_server + "/linkedin_posts.html?keywords={keywords}",
        userdata_dir=str(tmp_path / "userdata"),
        headless=True,
        executable_path=CHROMIUM,
        browser_args=("--no-sandbox",),
    )


def _settings(cap=25, idle=3):
    return {
        "discover": {
            "max_posts_per_run": cap,
            "max_run_minutes": 2,
            "max_idle_scrolls": idle,
            # Real runs pace in whole seconds; the harness only needs the code
            # path, not the wait.
            "delays": {"min_seconds": 0.01, "max_seconds": 0.03},
        }
    }


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "pipeline.db") as s:
        yield s


def test_captures_posts_from_a_realistic_page(store, env):
    from src.discover import run_discover

    result = run_discover(store, ["ai engineer"], _settings(), env)

    rows = store.get_by_status("captured")
    assert rows, f"captured nothing; stopped because {result.stop_reason}"
    assert result.stop_reason == STOP_SEARCHES_EXHAUSTED
    assert result.stored == len(rows)

    texts = {r["url_canonical"]: r["raw_text"] for r in rows}
    urls = set(texts)
    # Cards whose urn sits on the card element and on a descendant both work.
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000001/" in urls
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000002/" in urls


def test_urn_less_and_empty_cards_are_skipped_not_guessed(store, env):
    from src.discover import run_discover

    run_discover(store, ["ai engineer"], _settings(), env)
    rows = store.get_by_status("captured")

    # A card with no urn has no stable permalink — capturing it would give us a
    # post we can never dedupe or link back to, so it must be dropped.
    assert not any("Hiring backend engineers" in r["raw_text"] for r in rows)
    # An empty card yields no text worth storing.
    assert all(r["raw_text"].strip() for r in rows)


def test_repeated_urn_is_stored_once(store, env):
    from src.discover import run_discover

    run_discover(store, ["ai engineer"], _settings(), env)
    urls = [r["url_canonical"] for r in store.get_by_status("captured")]
    assert len(urls) == len(set(urls)), "the same post was stored twice"


def test_see_more_is_expanded_before_capture(store, env):
    from src.discover import run_discover

    run_discover(store, ["ai engineer"], _settings(), env)
    truncated = next(
        r for r in store.get_by_status("captured")
        if "Fernway" in r["raw_text"]
    )
    # The visible card shows ~60 chars behind a "…more" toggle. Missing the
    # click would silently truncate the work-auth line the qualify stage needs.
    assert "No sponsorship available" in truncated["raw_text"]
    assert "…" not in truncated["raw_text"]


def test_author_name_and_headline_are_captured(store, env):
    from src.discover import run_discover

    run_discover(store, ["ai engineer"], _settings(), env)
    row = next(
        r for r in store.get_by_status("captured") if "Northwind" in r["author"]
    )
    assert row["author"] == "Priya Raman — Talent Partner at Northwind AI"


def test_scrolling_loads_and_captures_the_next_page(store, env):
    from src.discover import run_discover

    run_discover(store, ["ai engineer"], _settings(), env)
    urls = {r["url_canonical"] for r in store.get_by_status("captured")}
    # These two only exist after the fixture lazy-loads on scroll.
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000006/" in urls
    assert "https://www.linkedin.com/feed/update/urn:li:activity:7100000000000000007/" in urls


def test_cap_is_enforced(store, env):
    from src.discover import run_discover

    result = run_discover(store, ["ai engineer"], _settings(cap=2), env)
    assert result.stored == 2
    assert result.stop_reason == STOP_CAP_REACHED
    assert len(store.get_by_status("captured")) == 2


def test_rerunning_is_idempotent(store, env):
    from src.discover import run_discover

    first = run_discover(store, ["ai engineer"], _settings(), env)
    second = run_discover(store, ["ai engineer"], _settings(), env)
    # Dedup is by canonical URL, so a second pass over the same page is a no-op.
    assert first.stored > 0
    assert second.stored == 0
    assert len(store.get_by_status("captured")) == first.stored


def test_captured_posts_flow_into_extraction(store, env):
    """The handoff that matters: what discovery stores must be usable
    downstream. Contact detection runs in code, so it needs no LLM."""
    from src.discover import run_discover
    from src.extract.emails import find_emails
    from src.extract.extract import _classify_contact, _heuristic_is_job_post

    run_discover(store, ["ai engineer"], _settings(), env)
    by_text = {r["raw_text"]: r for r in store.get_by_status("captured")}

    northwind = next(t for t in by_text if "LLM eval pipelines" in t)
    assert _heuristic_is_job_post(northwind)
    # Obfuscated address, as recruiters commonly write them.
    assert _classify_contact(northwind, find_emails(northwind)) == (
        "email", "priya@northwind.ai", False,
    )

    grove = next(t for t in by_text if "Grove Systems" in t)
    assert _classify_contact(grove, find_emails(grove))[1] == "careers@grovesystems.example"

    celebration = next(t for t in by_text if "Enormously proud" in t)
    assert not _heuristic_is_job_post(celebration)
