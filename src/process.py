"""Process orchestrator: extract -> qualify -> draft -> Gmail, from stored posts.

Runs entirely against SQLite — never touches LinkedIn. One post's failure sets
status=error and the batch continues; auth failures (Gmail/LLM) abort the run.
"""

from __future__ import annotations

import json
import logging

import anthropic

from src.draft import draft_email
from src.extract import extract_post, extracted_to_json
from src.gmail import GmailAuthError, create_draft, get_service
from src.models import ExtractedPost
from src.qualify import qualify_post
from src.settings import load_resume_text, load_rules, resume_pdf_path
from src.store import Store

logger = logging.getLogger("pipeline")

# Exceptions that must abort the whole run rather than mark one post as error.
FATAL = (GmailAuthError, anthropic.AuthenticationError, anthropic.PermissionDeniedError, KeyboardInterrupt)


def _guard(store: Store, url: str, stage: str):
    """Decorator-ish helper: run fn, on non-fatal failure mark error + continue."""

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc is None or (exc_type and issubclass(exc_type, FATAL)):
                return False  # propagate fatals, pass through success
            logger.error("%s failed for %s: %s", stage, url, exc)
            store.mark(url, "error", verdict_reason=f"{stage} error: {exc}")
            return True  # swallow, continue batch

    return _Ctx()


def stage_extract(store: Store, settings: dict) -> None:
    rows = store.get_by_status("captured")
    logger.info("extract: %d captured posts", len(rows))
    for row in rows:
        url = row["url_canonical"]
        with _guard(store, url, "extract"):
            post = extract_post(url, row["raw_text"], row["author"], settings)
            if not post.is_job_post:
                store.mark(url, "skipped", is_job_post=0, verdict_reason="not a job post")
                logger.info("skip (not a job post): %s", url)
                continue
            store.mark(
                url,
                "extracted",
                is_job_post=1,
                contact_method=post.contact_method,
                contact_email=post.contact_email,
                extracted_json=extracted_to_json(post),
                low_confidence=1 if post.low_confidence else 0,
            )
            logger.info("extracted: %s contact=%s", url, post.contact_method)


def _load_extracted(row) -> ExtractedPost:
    return ExtractedPost(**json.loads(row["extracted_json"]))


def stage_qualify(store: Store, settings: dict) -> None:
    rules = load_rules()
    rows = store.get_by_status("extracted")
    logger.info("qualify: %d extracted posts", len(rows))
    for row in rows:
        url = row["url_canonical"]
        if row["low_confidence"]:
            logger.warning("manual review needed (low confidence), holding: %s", url)
            continue  # stays 'extracted' until you inspect/clear it in the DB
        with _guard(store, url, "qualify"):
            post = _load_extracted(row)
            verdict = qualify_post(post, row["raw_text"], rules, settings)
            reason = f"[{verdict.source}] {verdict.reason}"
            if verdict.passed:
                store.mark(url, "qualified", verdict="pass", verdict_reason=reason)
                logger.info("PASS %s — %s", url, reason)
            else:
                store.mark(url, "skipped", verdict="reject", verdict_reason=reason)
                logger.info("reject %s — %s", url, reason)


def stage_draft(store: Store, settings: dict, dry_run: bool) -> None:
    rows = store.get_by_status("qualified")
    logger.info("draft: %d qualified posts (dry_run=%s)", len(rows), dry_run)
    if not rows:
        return
    resume_text = load_resume_text()
    resume_pdf = None if dry_run else resume_pdf_path()
    service = None if dry_run else get_service()

    for row in rows:
        url = row["url_canonical"]
        with _guard(store, url, "draft"):
            post = _load_extracted(row)
            if post.contact_method != "email" or not post.contact_email:
                store.mark(
                    url, "skipped",
                    verdict_reason=f"v2 candidate: contact via {post.contact_method}",
                )
                logger.info("skip (v2 candidate, contact=%s): %s", post.contact_method, url)
                continue
            result = draft_email(post, resume_text, settings)
            if result.flagged_terms:
                logger.warning(
                    "draft for %s mentions possibly off-resume terms %s — read carefully",
                    url, result.flagged_terms,
                )
            if dry_run:
                logger.info(
                    "DRY RUN draft for %s\n  To: %s\n  Subject: %s\n%s",
                    url, result.to_email, result.subject, result.body,
                )
                continue  # status stays 'qualified' so a real run picks it up
            draft_id = create_draft(service, result, resume_pdf)
            store.mark(url, "drafted", draft_id=draft_id)
            logger.info("drafted %s -> Gmail draft %s (to %s)", url, draft_id, result.to_email)


def run_process(store: Store, settings: dict, dry_run: bool, stages: list[str]) -> None:
    if "extract" in stages:
        stage_extract(store, settings)
    if "qualify" in stages:
        stage_qualify(store, settings)
    if "draft" in stages:
        stage_draft(store, settings, dry_run)
    logger.info("status counts: %s", store.counts_by_status())
