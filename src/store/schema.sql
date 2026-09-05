CREATE TABLE IF NOT EXISTS posts (
  url_canonical   TEXT PRIMARY KEY,
  raw_text        TEXT,
  author          TEXT,
  captured_at     TEXT,
  status          TEXT,        -- captured|extracted|qualified|drafted|skipped|error
  is_job_post     INTEGER,
  contact_method  TEXT,        -- email|dm|link|none|unknown
  contact_email   TEXT,
  extracted_json  TEXT,        -- parsed fields
  verdict         TEXT,        -- pass|reject
  verdict_reason  TEXT,
  draft_id        TEXT,        -- Gmail draft id
  low_confidence  INTEGER DEFAULT 0,
  updated_at      TEXT
);
