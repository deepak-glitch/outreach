"""Gmail: OAuth once, then drafts.create — the Drafts folder is the review queue.

Scope is gmail.compose only: this code can create drafts but never read your
inbox and never send. Every send is your click, in Gmail, by hand.
"""

from __future__ import annotations

import base64
import logging
import random
import time
from email.message import EmailMessage
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.models import DraftResult

logger = logging.getLogger("pipeline")

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_PATH = Path(".secrets/credentials.json")
TOKEN_PATH = Path(".secrets/token.json")


class GmailAuthError(RuntimeError):
    """Auth problems hard-fail the run — never silently skipped."""


def get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise GmailAuthError(
                f"token refresh failed ({exc}); delete .secrets/token.json and re-auth"
            ) from exc
    if not creds or not creds.valid:
        if not CREDENTIALS_PATH.exists():
            raise GmailAuthError(
                "missing .secrets/credentials.json — download the Desktop-app OAuth "
                "client from Google Cloud Console (see README prerequisites)"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        logger.info("stored refresh token at %s", TOKEN_PATH)
    return build("gmail", "v1", credentials=creds)


def _build_mime(draft: DraftResult, resume_pdf: Path) -> str:
    msg = EmailMessage()
    msg["To"] = draft.to_email
    msg["Subject"] = draft.subject
    msg.set_content(draft.body)
    msg.add_attachment(
        resume_pdf.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=resume_pdf.name,
    )
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def create_draft(service, draft: DraftResult, resume_pdf: Path, retries: int = 3) -> str:
    """Create the Gmail draft; returns the draft id."""
    body = {"message": {"raw": _build_mime(draft, resume_pdf)}}
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            created = service.users().drafts().create(userId="me", body=body).execute()
            return created["id"]
        except HttpError as exc:
            status = exc.resp.status if exc.resp else 0
            if status in (401, 403):
                raise GmailAuthError(f"Gmail auth error {status}: {exc}") from exc
            if status == 429 or status >= 500:
                last_exc = exc
                delay = min(2**attempt + random.uniform(0, 1), 30)
                logger.warning("Gmail %s; retry in %.1fs", status, delay)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError(f"drafts.create failed after {retries} attempts") from last_exc
