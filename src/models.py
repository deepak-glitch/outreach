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
