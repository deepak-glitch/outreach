"""Preflight checks — verify setup before anything touches the live session.

Discovery opens a real browser on Deepak's real LinkedIn account. Finding out
mid-pass that chromium is missing or the keywords file has a typo wastes a run
and, worse, leaves a half-finished session sitting on the screen. Checking
first is cheap; the skill layer runs this before every discover pass and reads
the result back to the user.

Each check returns a status the caller can act on:
  pass — good to go
  warn — works, but the user should know (e.g. first run needs a manual login)
  fail — broken

`status` is overall severity for the human; `blocks` lists the stages the
check gates. They differ on purpose: a missing resume is a `warn` overall
because discovery is unaffected, yet it still blocks `process`.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.guardrail import Guardrail

PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""
    blocks: list[str] = field(default_factory=list)  # stages this failure blocks


@dataclass
class PreflightReport:
    checks: list[Check]

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.status == WARN]

    def blocks(self, stage: str) -> list[Check]:
        """Checks gating `stage`.

        `blocks` is authoritative rather than `status`, because severity and
        gating are different questions: a missing resume is only a warning for
        the user overall (discovery runs fine without it) while still being a
        hard blocker for drafting. Only non-passing checks ever populate it.
        """
        return [c for c in self.checks if stage in c.blocks]

    def ok_for(self, stage: str) -> bool:
        return not self.blocks(stage)

    def to_dict(self) -> dict:
        return {
            "checks": [asdict(c) for c in self.checks],
            "ok_for_discover": self.ok_for("discover"),
            "ok_for_process": self.ok_for("process"),
            "failure_count": len(self.failures),
            "warning_count": len(self.warnings),
        }


def _check_config() -> list[Check]:
    checks = []
    required = {
        "config/settings.json": ["discover", "llm"],
        "config/keywords.json": ["searches"],
        "config/rules.json": ["work_auth", "employment_types_allowed"],
    }
    for path_str, expected_keys in required.items():
        path = Path(path_str)
        if not path.exists():
            checks.append(
                Check(
                    f"config: {path.name}",
                    FAIL,
                    f"{path_str} is missing",
                    f"restore {path_str} from the repo",
                    ["discover", "process"],
                )
            )
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            checks.append(
                Check(
                    f"config: {path.name}",
                    FAIL,
                    f"{path_str} is not valid JSON: {exc}",
                    f"fix the JSON syntax in {path_str}",
                    ["discover", "process"],
                )
            )
            continue
        missing = [k for k in expected_keys if k not in data]
        if missing:
            checks.append(
                Check(
                    f"config: {path.name}",
                    FAIL,
                    f"{path_str} is missing key(s): {', '.join(missing)}",
                    f"add the missing key(s) to {path_str}",
                    ["discover", "process"],
                )
            )
        else:
            checks.append(Check(f"config: {path.name}", PASS, "present and valid"))
    return checks


def _check_searches() -> Check:
    path = Path("config/keywords.json")
    if not path.exists():
        return Check("searches", FAIL, "no keywords file", "", ["discover"])
    try:
        searches = json.loads(path.read_text()).get("searches", [])
    except json.JSONDecodeError:
        return Check("searches", FAIL, "keywords.json unreadable", "", ["discover"])
    if not searches:
        return Check(
            "searches",
            FAIL,
            "no searches configured — discovery would do nothing",
            'add at least one query to "searches" in config/keywords.json',
            ["discover"],
        )
    return Check("searches", PASS, f"{len(searches)} configured: {', '.join(searches[:3])}")


def _check_browser() -> list[Check]:
    checks = []
    try:
        import playwright  # noqa: F401

        checks.append(Check("playwright", PASS, "installed"))
    except ImportError:
        checks.append(
            Check(
                "playwright",
                FAIL,
                "playwright is not installed",
                "pip install -r requirements.txt",
                ["discover"],
            )
        )
        return checks

    # Chromium lives in a browser cache whose location playwright only resolves
    # at launch. Probe rather than launching a browser to find out — and honour
    # PLAYWRIGHT_BROWSERS_PATH first, since managed and containerised setups
    # relocate the cache and would otherwise look like a missing install.
    roots = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        roots.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    roots += [Path.home() / ".cache/ms-playwright",
              Path.home() / "Library/Caches/ms-playwright",
              Path.home() / "AppData/Local/ms-playwright"]
    candidates = [c for root in roots for c in root.glob("chromium*")]
    if candidates or shutil.which("chromium") or shutil.which("chromium-browser"):
        checks.append(Check("chromium", PASS, "browser binary found"))
    else:
        checks.append(
            Check(
                "chromium",
                FAIL,
                "no chromium build found for playwright",
                "playwright install chromium",
                ["discover"],
            )
        )
    return checks


def _check_session() -> Check:
    userdata = Path(".userdata")
    if not userdata.exists() or not any(userdata.iterdir()):
        return Check(
            "linkedin session",
            WARN,
            "no saved session — this is a first run",
            "a browser will open; log in to LinkedIn by hand once and the "
            "session persists for later runs",
        )
    return Check("linkedin session", PASS, "saved session present in .userdata/")


def _check_resume() -> Check:
    txt, pdf = Path("config/resume.txt"), Path("config/resume.pdf")
    missing = [str(p) for p in (txt, pdf) if not p.exists()]
    if not missing:
        return Check("resume", PASS, "resume.txt and resume.pdf present")
    # Discovery does not need the resume; only drafting does.
    return Check(
        "resume",
        WARN,
        f"missing {', '.join(missing)} — discovery is fine, drafting will fail",
        "copy config/resume.example.txt to config/resume.txt and add resume.pdf",
        ["process"],
    )


def _check_storage() -> Check:
    try:
        Path("data").mkdir(parents=True, exist_ok=True)
        probe = Path("data/.write-probe")
        probe.write_text("ok")
        probe.unlink()
        return Check("storage", PASS, "data/ is writable")
    except OSError as exc:
        return Check(
            "storage", FAIL, f"cannot write to data/: {exc}", "check permissions",
            ["discover", "process"],
        )


def _check_guardrail(base_cap: int | None) -> Check:
    decision = Guardrail().check(base_cap)
    if decision.allowed and not decision.warnings:
        return Check("account guardrail", PASS, decision.reason)
    if decision.allowed:
        return Check("account guardrail", WARN, decision.reason,
                     f"resume at the reduced cap ({decision.recommended_cap})")
    return Check(
        "account guardrail",
        FAIL,
        decision.reason,
        "wait out the cooldown, or clear it after reviewing pacing",
        ["discover"],
    )


def run_preflight(base_cap: int | None = None) -> PreflightReport:
    checks: list[Check] = []
    checks.extend(_check_config())
    checks.append(_check_searches())
    checks.extend(_check_browser())
    checks.append(_check_session())
    checks.append(_check_resume())
    checks.append(_check_storage())
    checks.append(_check_guardrail(base_cap))
    return PreflightReport(checks)
