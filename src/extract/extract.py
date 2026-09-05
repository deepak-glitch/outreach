"""Extraction: raw post text -> ExtractedPost.

Order of operations (cheapest first):
  1. heuristic job-post gate — obvious non-job posts never reach the LLM
  2. one LLM call parses fields (and confirms is_job_post)
  3. code, not the LLM, owns contact_method/contact_email: regex + de-obfuscation
"""

from __future__ import annotations

import json
import logging
import re

from src.extract.emails import find_emails
from src.llm import complete_json
from src.models import ExtractedPost

logger = logging.getLogger("pipeline")

# If none of these appear, the post is very unlikely to be a job post.
JOB_HINTS = re.compile(
    r"\b(hiring|job|role|position|opening|opportunit|apply|applications?|"
    r"recruit|candidates?|resume|cv\b|join (?:our|the) team|looking for)\b",
    re.IGNORECASE,
)

DM_HINTS = re.compile(r"\b(dm me|dm us|send (?:me )?a dm|message me|inmail)\b", re.IGNORECASE)
LINK_HINTS = re.compile(
    r"(https?://\S+|\bapply (?:at|here|via|through)\b|link in (?:the )?comments?)",
    re.IGNORECASE,
)
# Emails visible only in an attached image often get referenced like this.
IMAGE_EMAIL_HINTS = re.compile(
    r"\b(email (?:in|on) (?:the )?(?:image|flyer|poster|below))\b", re.IGNORECASE
)

EXTRACT_SYSTEM = """You extract structured data from LinkedIn posts about job openings.
Reply with ONLY a JSON object, no prose, with exactly these keys:
{
  "is_job_post": bool,            // is this a post advertising one or more open roles?
  "title": string|null,           // primary role title
  "company": string|null,
  "recruiter": string|null,       // name of the person to contact, if stated
  "location": string|null,
  "remote": "remote"|"hybrid"|"onsite"|"unknown",
  "skills": [string],             // required skills/technologies
  "experience": string|null,      // required experience, verbatim-ish
  "employment_type": "full-time"|"contract"|"intern"|"unknown",
  "work_auth_wording": string|null, // VERBATIM visa/sponsorship/work-authorization wording, else null
  "low_confidence": bool          // true if the post is ambiguous or fields are guesses
}
Use null/"unknown"/[] when the post doesn't say. Never invent fields."""


def _heuristic_is_job_post(text: str) -> bool:
    return bool(JOB_HINTS.search(text))


def _classify_contact(text: str, emails: list[str]) -> tuple[str, str | None, bool]:
    """Returns (contact_method, contact_email, low_confidence)."""
    if emails:
        return "email", emails[0], len(emails) > 1  # multiple emails -> hand-check
    if IMAGE_EMAIL_HINTS.search(text):
        # Email likely lives in an image we didn't capture: route to manual review
        # rather than silently dropping (v1 decision: no OCR).
        return "email", None, True
    if DM_HINTS.search(text):
        return "dm", None, False
    if LINK_HINTS.search(text):
        return "link", None, False
    return "none", None, False


def extract_post(url_canonical: str, raw_text: str, author: str, settings: dict) -> ExtractedPost:
    if not _heuristic_is_job_post(raw_text):
        return ExtractedPost(url_canonical=url_canonical, is_job_post=False)

    parsed = complete_json(
        model=settings["llm"]["cheap_model"],
        system=EXTRACT_SYSTEM,
        user=f"Author: {author}\n\nPost:\n{raw_text}",
        max_tokens=1024,
    )

    emails = find_emails(raw_text)
    contact_method, contact_email, contact_low_conf = _classify_contact(raw_text, emails)

    return ExtractedPost(
        url_canonical=url_canonical,
        is_job_post=bool(parsed.get("is_job_post")),
        title=parsed.get("title"),
        company=parsed.get("company"),
        recruiter=parsed.get("recruiter"),
        location=parsed.get("location"),
        remote=parsed.get("remote") or "unknown",
        skills=[s for s in parsed.get("skills") or [] if isinstance(s, str)],
        experience=parsed.get("experience"),
        employment_type=parsed.get("employment_type") or "unknown",
        work_auth_wording=parsed.get("work_auth_wording"),
        contact_method=contact_method,
        contact_email=contact_email,
        low_confidence=bool(parsed.get("low_confidence")) or contact_low_conf,
    )


def extracted_to_json(post: ExtractedPost) -> str:
    return json.dumps(post.to_dict(), ensure_ascii=False)
