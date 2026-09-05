"""The discover result is the contract the skill layer reads. If these shapes
drift, the skill silently misreports what happened on a live scrape."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.models import (
    BENIGN_STOPS,
    STOP_CAP_REACHED,
    STOP_LOGIN_WALL,
    STOP_RATE_LIMIT,
    STOP_SELECTOR_DRIFT,
    WARNING_STOPS,
    DiscoverResult,
)

REPO = Path(__file__).resolve().parent.parent


def test_result_serializes_for_json_output():
    payload = DiscoverResult(
        stored=7, cap=25, searches_run=2, searches_total=3,
        stop_reason=STOP_CAP_REACHED, stop_detail="hit the 25-post cap",
        duration_seconds=91.4,
    ).to_dict()
    assert json.loads(json.dumps(payload))["stop_reason"] == STOP_CAP_REACHED
    # Every field the SKILL.md instructs the skill to read must be present.
    assert set(payload) >= {"stored", "cap", "stop_reason", "stop_detail", "warning_recorded"}


def test_warning_and_benign_stops_are_disjoint():
    # A stop reason that is both benign and a warning would make the guardrail
    # fire on healthy runs (or worse, not fire on unhealthy ones).
    assert not (BENIGN_STOPS & WARNING_STOPS)


def test_linkedin_interstitials_count_as_warnings():
    assert STOP_RATE_LIMIT in WARNING_STOPS
    assert STOP_LOGIN_WALL in WARNING_STOPS


def test_selector_drift_is_not_a_linkedin_warning():
    # Our selectors rotting is our problem, not a signal from LinkedIn — it
    # must not consume one of the two warnings that halt discovery.
    assert STOP_SELECTOR_DRIFT not in WARNING_STOPS
    assert STOP_SELECTOR_DRIFT not in BENIGN_STOPS


def _run_cli(cwd, *args):
    return subprocess.run(
        [sys.executable, str(REPO / "run.py"), *args],
        cwd=cwd, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO), "HOME": str(cwd)},
    )


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "config").mkdir()
    for name in ("settings.json", "keywords.json", "rules.json"):
        (tmp_path / "config" / name).write_text((REPO / "config" / name).read_text())
    return tmp_path


def test_cli_discover_refuses_when_guardrail_is_up(workspace):
    from src.guardrail import Guardrail

    (workspace / "data").mkdir()
    Guardrail(workspace / "data" / "guardrail.json").record_warning(
        "rate_limit_warning", "security check"
    )
    result = _run_cli(workspace, "discover", "--json")
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["blocked"] is True
    assert any("guardrail" in b["name"] for b in payload["blockers"])


def test_cli_guardrail_clear_unblocks(workspace):
    from src.guardrail import Guardrail

    (workspace / "data").mkdir()
    Guardrail(workspace / "data" / "guardrail.json").record_warning(
        "rate_limit_warning", "security check"
    )
    assert _run_cli(workspace, "guardrail").returncode == 1
    _run_cli(workspace, "guardrail", "--clear", "halved cap, longer delays")
    assert _run_cli(workspace, "guardrail").returncode == 0
