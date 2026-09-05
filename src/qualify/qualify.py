"""Qualification: hard code filters first (auditable), LLM relevance second.

Every rejection carries a human-readable verdict_reason — the DB row must
explain itself six weeks from now.
"""

from __future__ import annotations

import logging

from src.llm import complete_json
from src.models import ExtractedPost, Verdict

logger = logging.getLogger("pipeline")

RELEVANCE_SYSTEM = """You screen job posts for a candidate. Given the candidate's
target-role description and a parsed job post, decide if the role is genuinely
worth pursuing (a real match for the target), not merely adjacent to it.
Reply with ONLY a JSON object: {"pass": bool, "reason": string}
The reason must be one short, concrete sentence."""


def _contains_any(haystack: str | None, phrases: list[str]) -> str | None:
    if not haystack:
        return None
    lowered = haystack.lower()
    for phrase in phrases:
        if phrase.lower() in lowered:
            return phrase
    return None


def apply_hard_filters(post: ExtractedPost, raw_text: str, rules: dict) -> Verdict | None:
    """Code-only filters from config/rules.json. Returns a reject Verdict or None."""
    url = post.url_canonical

    hit = _contains_any(post.work_auth_wording, rules["work_auth"]["reject_phrases"])
    if hit is None:
        hit = _contains_any(raw_text, rules["work_auth"]["reject_phrases"])
    if hit:
        return Verdict(url, False, f"work-auth: post says {hit!r}", "rules")

    allowed_types = [t.lower() for t in rules["employment_types_allowed"]]
    if post.employment_type not in ("unknown", None) and post.employment_type.lower() not in allowed_types:
        return Verdict(
            url, False, f"employment type {post.employment_type!r} not in allowed list", "rules"
        )

    loc = rules["location"]
    if loc.get("remote_required") and post.remote == "onsite":
        allowed_hit = _contains_any(post.location, loc.get("allowed_locations", []))
        if not allowed_hit:
            return Verdict(
                url, False, f"onsite role in {post.location!r}, remote required", "rules"
            )
    return None


def llm_relevance(post: ExtractedPost, rules: dict, settings: dict) -> Verdict:
    result = complete_json(
        model=settings["llm"]["cheap_model"],
        system=RELEVANCE_SYSTEM,
        user=(
            f"Candidate target: {rules['target_role_description']}\n\n"
            f"Parsed job post:\n"
            f"  title: {post.title}\n  company: {post.company}\n"
            f"  skills: {', '.join(post.skills) or 'unknown'}\n"
            f"  experience: {post.experience}\n  location: {post.location} ({post.remote})\n"
            f"  employment type: {post.employment_type}"
        ),
        max_tokens=256,
    )
    return Verdict(
        post.url_canonical,
        bool(result.get("pass")),
        str(result.get("reason") or "no reason given"),
        "llm",
    )


def qualify_post(post: ExtractedPost, raw_text: str, rules: dict, settings: dict) -> Verdict:
    rejected = apply_hard_filters(post, raw_text, rules)
    if rejected:
        return rejected
    return llm_relevance(post, rules, settings)
