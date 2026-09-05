"""SQLite persistence: dedup, status transitions, audit trail.

The posts table is the single source of truth for the pipeline. Every state
change stamps updated_at so the table doubles as an audit log.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import RawPost

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path("data/pipeline.db")

# Columns mark() is allowed to touch besides status/updated_at.
_MUTABLE_FIELDS = {
    "is_job_post",
    "contact_method",
    "contact_email",
    "extracted_json",
    "verdict",
    "verdict_reason",
    "draft_id",
    "low_confidence",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def exists(self, url_canonical: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM posts WHERE url_canonical = ?", (url_canonical,)
        ).fetchone()
        return row is not None

    def upsert_raw(self, post: RawPost) -> bool:
        """Insert a freshly captured post. Returns False on duplicate (no-op)."""
        if self.exists(post.url_canonical):
            return False
        self.conn.execute(
            "INSERT INTO posts (url_canonical, raw_text, author, captured_at,"
            " status, updated_at) VALUES (?, ?, ?, ?, 'captured', ?)",
            (post.url_canonical, post.raw_text, post.author, post.captured_at, _now()),
        )
        self.conn.commit()
        return True

    def mark(self, url_canonical: str, status: str, **fields) -> None:
        unknown = set(fields) - _MUTABLE_FIELDS
        if unknown:
            raise ValueError(f"mark() got unknown fields: {unknown}")
        sets = ["status = ?", "updated_at = ?"]
        params: list = [status, _now()]
        for key, value in fields.items():
            sets.append(f"{key} = ?")
            params.append(value)
        params.append(url_canonical)
        self.conn.execute(
            f"UPDATE posts SET {', '.join(sets)} WHERE url_canonical = ?", params
        )
        self.conn.commit()

    def get_by_status(self, status: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM posts WHERE status = ? ORDER BY captured_at", (status,)
        ).fetchall()

    def counts_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM posts GROUP BY status"
        ).fetchall()
        return {row["status"]: row["n"] for row in rows}
