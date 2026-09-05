"""Email detection and de-obfuscation for post text."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# name [at] company [dot] com, name (at) company dot com, "name at company dot com"
_AT = r"(?:\s*[\[\(\{]\s*at\s*[\]\)\}]\s*|\s+at\s+|\s*@\s*)"
_DOT = r"(?:\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*|\s+dot\s+|\s*\.\s*)"
OBFUSCATED_RE = re.compile(
    rf"([A-Za-z0-9._%+-]+){_AT}([A-Za-z0-9-]+(?:{_DOT}[A-Za-z0-9-]+)+)",
    re.IGNORECASE,
)
_DOT_SPLIT = re.compile(_DOT, re.IGNORECASE)

# A candidate only counts as an obfuscated email if it carries an explicit
# obfuscation marker — otherwise "reach me at acme.com" style prose matches.
_MARKER_RE = re.compile(
    r"[\[\(\{]\s*(?:at|dot)\s*[\]\)\}]|\sdot\s|@", re.IGNORECASE
)


def find_emails(text: str) -> list[str]:
    """Standard emails plus de-obfuscated ones, deduped, order preserved."""
    found: list[str] = []

    def add(email: str) -> None:
        email = email.strip(".").lower()
        if EMAIL_RE.fullmatch(email) and email not in found:
            found.append(email)

    for match in EMAIL_RE.finditer(text):
        add(match.group(0))
    # Mask real emails so the obfuscation pass can't cannibalize their text
    # ("reach me at jane.doe@acme.com" must not also yield "me@jane.doe").
    masked = EMAIL_RE.sub(lambda m: "\x00" * len(m.group(0)), text)
    for match in OBFUSCATED_RE.finditer(masked):
        if not _MARKER_RE.search(match.group(0)):
            continue
        local = match.group(1)
        domain = ".".join(p for p in _DOT_SPLIT.split(match.group(2)) if p)
        add(f"{local}@{domain}")
    return found
