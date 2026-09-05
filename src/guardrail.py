"""Account-safety guardrail — PRD §8 stop conditions, enforced in code.

The LinkedIn account runs Deepak's live interviews; it is the asset the whole
project exists to protect. Kickoff agreed the stop conditions are
non-negotiable, so they live here as code rather than as a line in a runbook
somebody remembers at 11pm:

  1st warning  → discovery blocked for a cooldown window, cap halved on resume
  2nd warning  → discovery blocked until a human reviews and clears it

State is a small JSON file under data/. It is deliberately plain text: the only
way past a block is for a person to open it and decide, which is exactly the
friction we want at that moment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_STATE_PATH = Path("data/guardrail.json")
COOLDOWN_HOURS = 48
REVIEW_THRESHOLD = 2  # warnings before a human must clear it

# check() verdicts
OK = "ok"
COOLDOWN = "cooldown"
REVIEW_REQUIRED = "review_required"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    parsed = datetime.fromisoformat(ts)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Decision:
    verdict: str
    allowed: bool
    reason: str
    recommended_cap: int | None = None
    resume_at: str | None = None
    warnings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "allowed": self.allowed,
            "reason": self.reason,
            "recommended_cap": self.recommended_cap,
            "resume_at": self.resume_at,
            "warning_count": len(self.warnings),
        }


class Guardrail:
    def __init__(self, path: Path | str = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self.state = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"warnings": [], "cleared_at": None}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            # A corrupt guardrail file must fail safe: treat it as a warning
            # state rather than silently granting permission to scrape.
            return {
                "warnings": [
                    {
                        "at": _now().isoformat(timespec="seconds"),
                        "kind": "corrupt_state",
                        "detail": f"unreadable guardrail file at {self.path}",
                    }
                ],
                "cleared_at": None,
            }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2) + "\n")

    def active_warnings(self) -> list[dict]:
        """Warnings since the last human clear."""
        cleared_at = self.state.get("cleared_at")
        warnings = self.state.get("warnings", [])
        if not cleared_at:
            return warnings
        cutoff = _parse(cleared_at)
        return [w for w in warnings if _parse(w["at"]) > cutoff]

    def record_warning(self, kind: str, detail: str) -> Decision:
        self.state.setdefault("warnings", []).append(
            {"at": _now().isoformat(timespec="seconds"), "kind": kind, "detail": detail}
        )
        self._save()
        return self.check()

    def clear(self, note: str = "") -> None:
        """Human review done — resume discovery. Deliberately explicit."""
        self.state["cleared_at"] = _now().isoformat(timespec="seconds")
        self.state["clear_note"] = note
        self._save()

    def check(self, base_cap: int | None = None) -> Decision:
        active = self.active_warnings()
        if not active:
            return Decision(OK, True, "no LinkedIn warnings on record", base_cap)

        if len(active) >= REVIEW_THRESHOLD:
            return Decision(
                REVIEW_REQUIRED,
                False,
                f"{len(active)} LinkedIn warnings since the last review. PRD §8 stops "
                f"discovery until a human reviews pacing. Clear with: "
                f"python run.py guardrail --clear \"<what you changed>\"",
                recommended_cap=None,
                warnings=active,
            )

        last = active[-1]
        resume_at = _parse(last["at"]) + timedelta(hours=COOLDOWN_HOURS)
        # Each warning halves the cap we recommend on resume.
        halved = max(5, base_cap // (2 ** len(active))) if base_cap else None
        if _now() < resume_at:
            remaining = resume_at - _now()
            hours = round(remaining.total_seconds() / 3600, 1)
            return Decision(
                COOLDOWN,
                False,
                f"LinkedIn warning on {last['at']} ({last['kind']}). Cooling down "
                f"{COOLDOWN_HOURS}h — {hours}h left. Do not push.",
                recommended_cap=halved,
                resume_at=resume_at.isoformat(timespec="seconds"),
                warnings=active,
            )
        return Decision(
            OK,
            True,
            f"cooldown from the {last['at']} warning has elapsed; resume at a "
            f"reduced cap ({halved}) and watch for a repeat",
            recommended_cap=halved,
            warnings=active,
        )
