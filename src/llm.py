"""Shared LLM helper: one place that talks to the Claude API.

The SDK already retries 429/5xx with backoff; we add one outer retry ring for
transient failures and hard-fail (never silently skip) on auth errors.
"""

from __future__ import annotations

import json
import logging
import random
import time

import anthropic

from src.settings import ensure_llm_key

logger = logging.getLogger("pipeline")

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        ensure_llm_key()
        _client = anthropic.Anthropic()
    return _client


def complete_text(
    *, model: str, system: str, user: str, max_tokens: int = 2048, retries: int = 3
) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = client().messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in response.content if b.type == "text")
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise  # auth problems must stop the run, not be skipped
        except anthropic.BadRequestError:
            raise  # our bug; retrying the same request cannot help
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            delay = min(2**attempt + random.uniform(0, 1), 30)
            logger.warning("LLM call failed (%s); retry in %.1fs", exc, delay)
            time.sleep(delay)
    raise RuntimeError(f"LLM call failed after {retries} attempts") from last_exc


def complete_json(
    *, model: str, system: str, user: str, max_tokens: int = 2048
) -> dict:
    """Call the model and parse the first JSON object out of its reply."""
    text = complete_text(model=model, system=system, user=user, max_tokens=max_tokens)
    return extract_json_object(text)


def extract_json_object(text: str) -> dict:
    """Pull the first balanced {...} out of text (tolerates prose/code fences)."""
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in LLM reply: {text[:200]!r}")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"unbalanced JSON in LLM reply: {text[:200]!r}")
