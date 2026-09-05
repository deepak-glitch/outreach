"""URL canonicalization — the dedup key for everything downstream."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_ACTIVITY_RE = re.compile(r"urn:li:(?:activity|share|ugcPost):(\d+)")
# /posts/jane-doe_hiring-activity-7207360479201822720-Ab_c share URLs
_POSTS_ACTIVITY_RE = re.compile(r"[-/]activity-(\d{10,25})(?:[-/?]|$)")


def canonicalize_url(url_or_urn: str) -> str:
    """Reduce a post link (or a data-urn attribute) to a stable canonical form.

    Tracking params, locale prefixes, and mirror paths all collapse to
    https://www.linkedin.com/feed/update/urn:li:activity:<id>/ when an
    activity id is present; otherwise scheme+host+path with the query stripped.
    """
    match = _ACTIVITY_RE.search(url_or_urn) or _POSTS_ACTIVITY_RE.search(url_or_urn)
    if match:
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{match.group(1)}/"
    parsed = urlparse(url_or_urn)
    path = parsed.path.rstrip("/") + "/"
    return f"{parsed.scheme or 'https'}://{parsed.netloc or 'www.linkedin.com'}{path}"
