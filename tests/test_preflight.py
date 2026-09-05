"""Preflight tests — these checks are what stand between a typo in a config
file and a wasted pass on the user's live LinkedIn session."""

import json
import os
from pathlib import Path

import pytest

from src.preflight import FAIL, PASS, WARN, run_preflight

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def stub_browser(monkeypatch):
    """Browser availability is a property of the machine running the tests, not
    of the logic under test — stub it so these assertions stay meaningful on a
    CI box with no chromium. `test_browser_check_*` cover the real thing."""
    import src.preflight as pf

    monkeypatch.setattr(
        pf, "_check_browser", lambda: [pf.Check("playwright", PASS, "stubbed"),
                                       pf.Check("chromium", PASS, "stubbed")]
    )


@pytest.fixture
def workspace(tmp_path, monkeypatch, stub_browser):
    """A minimal valid repo layout in a temp dir, cwd'd into."""
    (tmp_path / "config").mkdir()
    for name in ("settings.json", "keywords.json", "rules.json"):
        (tmp_path / "config" / name).write_text((REPO / "config" / name).read_text())
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _check(report, name):
    return next(c for c in report.checks if c.name == name)


def test_valid_workspace_is_ready_for_discover(workspace):
    report = run_preflight(25)
    # Missing resume/session are warnings, not discover blockers.
    assert report.ok_for("discover")
    assert _check(report, "searches").status == PASS


def test_missing_config_blocks_both_stages(workspace):
    (workspace / "config" / "rules.json").unlink()
    report = run_preflight(25)
    assert not report.ok_for("discover")
    assert not report.ok_for("process")
    assert _check(report, "config: rules.json").status == FAIL


def test_malformed_json_is_reported_as_such(workspace):
    (workspace / "config" / "settings.json").write_text("{oops")
    check = _check(run_preflight(25), "config: settings.json")
    assert check.status == FAIL
    assert "not valid JSON" in check.detail


def test_config_missing_required_key_is_caught(workspace):
    (workspace / "config" / "settings.json").write_text(json.dumps({"llm": {}}))
    check = _check(run_preflight(25), "config: settings.json")
    assert check.status == FAIL
    assert "discover" in check.detail


def test_empty_searches_blocks_discover(workspace):
    (workspace / "config" / "keywords.json").write_text(json.dumps({"searches": []}))
    report = run_preflight(25)
    assert not report.ok_for("discover")
    assert "would do nothing" in _check(report, "searches").detail


def test_first_run_session_is_a_warning_not_a_block(workspace):
    report = run_preflight(25)
    check = _check(report, "linkedin session")
    assert check.status == WARN
    assert report.ok_for("discover")


def test_existing_session_passes(workspace):
    userdata = workspace / ".userdata"
    userdata.mkdir()
    (userdata / "Default").write_text("session")
    assert _check(run_preflight(25), "linkedin session").status == PASS


def test_missing_resume_blocks_process_but_not_discover(workspace):
    report = run_preflight(25)
    check = _check(report, "resume")
    assert check.status == WARN
    assert report.ok_for("discover")
    assert not report.ok_for("process")


def test_present_resume_passes(workspace):
    (workspace / "config" / "resume.txt").write_text("JANE DOE")
    (workspace / "config" / "resume.pdf").write_bytes(b"%PDF-1.4")
    report = run_preflight(25)
    assert _check(report, "resume").status == PASS
    assert report.ok_for("process")


def test_guardrail_warning_blocks_discover(workspace):
    from src.guardrail import Guardrail

    (workspace / "data").mkdir(exist_ok=True)
    Guardrail(workspace / "data" / "guardrail.json").record_warning(
        "rate_limit_warning", "security check"
    )
    report = run_preflight(25)
    assert not report.ok_for("discover")
    assert _check(report, "account guardrail").status == FAIL


def test_report_serializes_for_the_skill_layer(workspace):
    payload = run_preflight(25).to_dict()
    assert set(payload) >= {"checks", "ok_for_discover", "ok_for_process"}
    assert isinstance(payload["ok_for_discover"], bool)
    json.dumps(payload)  # must survive --json


def test_browser_check_reports_missing_playwright(monkeypatch):
    """When playwright is genuinely absent, say so and block discover rather
    than letting the import blow up mid-run."""
    import builtins

    import src.preflight as pf

    real_import = builtins.__import__

    def no_playwright(name, *a, **kw):
        if name == "playwright":
            raise ImportError("stubbed missing")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_playwright)
    checks = pf._check_browser()
    assert checks[0].status == FAIL
    assert "discover" in checks[0].blocks
    assert "pip install" in checks[0].fix
