"""Typed stage objects — the contracts between pipeline stages.

Each stage consumes the previous stage's object and produces the next:

    discover -> RawPost -> extract -> ExtractedPost -> qualify -> Verdict
                                                    -> draft -> DraftResult
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class RawPost:
    """What discover captures from a LinkedIn post card. No parsing — raw only."""

    url_canonical: str
    raw_text: str
    author: str  # "Name — headline" as scraped
    captured_at: str  # ISO-8601 UTC

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedPost:
    """Structured fields parsed from a RawPost."""

    url_canonical: str
    is_job_post: bool
    title: Optional[str] = None
    company: Optional[str] = None
    recruiter: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[str] = None  # remote|hybrid|onsite|unknown
    skills: list[str] = field(default_factory=list)
    experience: Optional[str] = None
    employment_type: Optional[str] = None  # full-time|contract|intern|unknown
    work_auth_wording: Optional[str] = None  # verbatim visa/sponsorship phrasing
    contact_method: str = "unknown"  # email|dm|link|none|unknown
    contact_email: Optional[str] = None
    low_confidence: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    """Qualification outcome. `source` records whether code rules or the LLM decided."""

    url_canonical: str
    passed: bool
    reason: str
    source: str  # "rules" | "llm"


@dataclass
class DraftResult:
    """A generated outreach email, before it becomes a Gmail draft."""

    url_canonical: str
    to_email: str
    subject: str
    body: str
    flagged_terms: list[str] = field(default_factory=list)  # possible off-resume claims


@dataclass
class DiscoverResult:
    """Outcome of one discover pass — what the skill layer narrates to the user.

    `stop_reason` matters more than the count: a run that stopped because
    LinkedIn showed an interstitial is a safety event, not a small harvest.
    """

    stored: int
    cap: int
    searches_run: int
    searches_total: int
    stop_reason: str  # see STOP_REASONS
    stop_detail: str
    duration_seconds: float
    warning_recorded: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# Benign stops — the pass did its job and ended on a limit we set.
STOP_CAP_REACHED = "cap_reached"
STOP_WINDOW_ELAPSED = "window_elapsed"
STOP_SEARCHES_EXHAUSTED = "searches_exhausted"
STOP_USER_INTERRUPT = "user_interrupt"
# Attention stops — something about LinkedIn or our selectors needs a human.
STOP_RATE_LIMIT = "rate_limit_warning"
STOP_LOGIN_WALL = "login_wall"
STOP_SELECTOR_DRIFT = "selector_drift"
STOP_NO_RESULTS = "no_results"

BENIGN_STOPS = frozenset(
    {STOP_CAP_REACHED, STOP_WINDOW_ELAPSED, STOP_SEARCHES_EXHAUSTED, STOP_USER_INTERRUPT}
)
# Stops that count as a LinkedIn warning under PRD §8 and trip the guardrail.
WARNING_STOPS = frozenset({STOP_RATE_LIMIT, STOP_LOGIN_WALL})
