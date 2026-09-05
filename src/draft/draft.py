"""Drafting: (full resume + parsed post) -> short, job-specific recruiter email.

Anti-hallucination is structural: the resume is the ONLY experience source in
context. A cheap output check then flags post skills the draft claims but the
resume never mentions.
"""

from __future__ import annotations

import logging
import re

from src.llm import complete_json
from src.models import DraftResult, ExtractedPost

logger = logging.getLogger("pipeline")

DRAFT_SYSTEM = """You write short outreach emails from a job seeker to a recruiter
who posted an open role on LinkedIn.

Hard rules:
- The candidate's resume below is the ONLY source of their experience. Never
  claim any skill, tool, employer, degree, or accomplishment that is not in it.
- If the role asks for something the resume lacks, do not pretend — either omit
  it or honestly note adjacent experience.
- 120 words max in the body. Specific to THIS role. No flattery, no buzzwords.
- Mention that the resume is attached. Sign with the candidate's name as it
  appears on the resume.

Reply with ONLY a JSON object: {"subject": string, "body": string}"""


def draft_email(post: ExtractedPost, resume_text: str, settings: dict) -> DraftResult:
    if post.contact_method != "email" or not post.contact_email:
        raise ValueError(f"{post.url_canonical}: no email contact, cannot draft")

    result = complete_json(
        model=settings["llm"]["draft_model"],
        system=DRAFT_SYSTEM,
        user=(
            f"CANDIDATE RESUME (sole experience source):\n{resume_text}\n\n"
            f"JOB POST:\n"
            f"  title: {post.title}\n  company: {post.company}\n"
            f"  recruiter: {post.recruiter}\n"
            f"  skills wanted: {', '.join(post.skills) or 'not stated'}\n"
            f"  experience wanted: {post.experience}\n"
            f"  location: {post.location} ({post.remote})"
        ),
        max_tokens=1024,
    )
    subject = str(result.get("subject") or "").strip()
    body = str(result.get("body") or "").strip()
    if not subject or not body:
        raise ValueError(f"{post.url_canonical}: draft came back empty")

    return DraftResult(
        url_canonical=post.url_canonical,
        to_email=post.contact_email,
        subject=subject,
        body=body,
        flagged_terms=flag_off_resume_claims(body, post.skills, resume_text),
    )


def flag_off_resume_claims(body: str, post_skills: list[str], resume_text: str) -> list[str]:
    """Post skills the draft claims but the resume never mentions.

    Crude by design — a flag means "read this one extra carefully in Gmail",
    not "reject".
    """
    resume_lower = resume_text.lower()
    body_lower = body.lower()
    flagged = []
    for skill in post_skills:
        s = skill.strip().lower()
        if not s:
            continue
        pattern = r"\b" + re.escape(s) + r"\b"
        if re.search(pattern, body_lower) and not re.search(pattern, resume_lower):
            flagged.append(skill)
    return flagged
