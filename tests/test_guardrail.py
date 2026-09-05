"""Guardrail tests — this module encodes the PRD §8 account-safety stop
conditions, so a regression here is a regression in the one thing the project
promised never to get wrong."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.guardrail import COOLDOWN, OK, REVIEW_REQUIRED, Guardrail


@pytest.fixture
def rail(tmp_path):
    return Guardrail(tmp_path / "guardrail.json")


def _hours_ago(n):
    return (datetime.now(timezone.utc) - timedelta(hours=n)).isoformat(timespec="seconds")


def test_clean_state_allows_discovery(rail):
    decision = rail.check(base_cap=25)
    assert decision.verdict == OK
    assert decision.allowed
    assert decision.recommended_cap == 25


def test_first_warning_blocks_and_halves_cap(rail):
    decision = rail.record_warning("rate_limit_warning", "security check")
    assert decision.verdict == COOLDOWN
    assert not decision.allowed
    assert "do not push" in decision.reason.lower()


def test_cap_halves_per_warning(rail):
    rail.record_warning("rate_limit_warning", "first")
    assert rail.check(base_cap=40).recommended_cap == 20


def test_cooldown_expires_after_48h(rail, tmp_path):
    rail.state["warnings"] = [{"at": _hours_ago(49), "kind": "rate_limit_warning", "detail": "old"}]
    rail._save()
    decision = Guardrail(tmp_path / "guardrail.json").check(base_cap=40)
    assert decision.allowed
    # Still recommends the reduced cap — the warning happened, even if the wait is over.
    assert decision.recommended_cap == 20


def test_second_warning_requires_human_review(rail):
    rail.record_warning("rate_limit_warning", "first")
    decision = rail.record_warning("login_wall", "second")
    assert decision.verdict == REVIEW_REQUIRED
    assert not decision.allowed
    assert "--clear" in decision.reason


def test_review_required_does_not_expire_with_time(rail, tmp_path):
    rail.state["warnings"] = [
        {"at": _hours_ago(500), "kind": "rate_limit_warning", "detail": "old"},
        {"at": _hours_ago(499), "kind": "rate_limit_warning", "detail": "older"},
    ]
    rail._save()
    # Two warnings need a person, no matter how long ago they were.
    assert not Guardrail(tmp_path / "guardrail.json").check(40).allowed


def test_clear_resets_and_unblocks(rail, tmp_path):
    rail.record_warning("rate_limit_warning", "first")
    rail.record_warning("login_wall", "second")
    rail.clear("lengthened delays, halved cap")
    reloaded = Guardrail(tmp_path / "guardrail.json")
    assert reloaded.check(25).allowed
    assert reloaded.active_warnings() == []
    # History is kept for the audit trail even though it no longer blocks.
    assert len(reloaded.state["warnings"]) == 2


def test_corrupt_state_fails_safe(tmp_path):
    path = tmp_path / "guardrail.json"
    path.write_text("{not json at all")
    # A guardrail we cannot read must never be read as "you're clear to scrape".
    assert not Guardrail(path).check(25).allowed


def test_state_survives_reload(rail, tmp_path):
    rail.record_warning("rate_limit_warning", "security check")
    saved = json.loads((tmp_path / "guardrail.json").read_text())
    assert saved["warnings"][0]["kind"] == "rate_limit_warning"
    assert not Guardrail(tmp_path / "guardrail.json").check(25).allowed
