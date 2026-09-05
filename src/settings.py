"""Config loading. All tunables live in config/, not in code."""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path("config")
SECRETS_DIR = Path(".secrets")


def load_settings(path: Path | None = None) -> dict:
    settings_path = path or CONFIG_DIR / "settings.json"
    return json.loads(settings_path.read_text())


def load_rules(path: Path | None = None) -> dict:
    rules_path = path or CONFIG_DIR / "rules.json"
    return json.loads(rules_path.read_text())


def load_keywords(path: Path | None = None) -> list[str]:
    kw_path = path or CONFIG_DIR / "keywords.json"
    data = json.loads(kw_path.read_text())
    return data["searches"]


def load_resume_text() -> str:
    resume_path = CONFIG_DIR / "resume.txt"
    if not resume_path.exists():
        raise FileNotFoundError(
            "config/resume.txt not found. Copy config/resume.example.txt to "
            "config/resume.txt and fill in your real resume — the drafter refuses "
            "to run without it."
        )
    return resume_path.read_text()


def resume_pdf_path() -> Path:
    pdf = CONFIG_DIR / "resume.pdf"
    if not pdf.exists():
        raise FileNotFoundError(
            "config/resume.pdf not found — it is the attachment sent to recruiters."
        )
    return pdf


def ensure_llm_key() -> None:
    """The anthropic SDK reads ANTHROPIC_API_KEY; fall back to .secrets/llm_key."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    key_file = SECRETS_DIR / "llm_key"
    if key_file.exists():
        os.environ["ANTHROPIC_API_KEY"] = key_file.read_text().strip()
        return
    raise RuntimeError(
        "No LLM API key: set ANTHROPIC_API_KEY or put the key in .secrets/llm_key"
    )
