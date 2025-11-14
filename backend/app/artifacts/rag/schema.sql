-- ============================================================
-- rag.sqlite schema (doc table + FTS + helper views)
-- ============================================================

PRAGMA journal_mode=WAL;

-- ------------------------------------------------------------
-- Base table for evidence documents
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doc (
  doc_id        TEXT PRIMARY KEY,         -- e.g. "14b92d4a/mml_2.block_has_port/block/425"
  model_id      TEXT,
  vendor        TEXT,
  version       TEXT,
  mml           INTEGER,
  probe_id      TEXT,                     -- normalized: "mml_2.block_has_port"
  doc_type      TEXT,                     -- "summary" | "block" | "entity" | ...
  subject_type  TEXT,                     -- "block" | "port" | ...
  subject_id    TEXT,
  title         TEXT,
  ctx_hdr       TEXT,
  body_text     TEXT,
  json_metadata TEXT,
  ts_ms         INTEGER
);

-- ------------------------------------------------------------
-- FTS5 over searchable text (RECREATED with custom separators)
-- NOTE: The tokenize directive must be a single-quoted string.
--       Option values inside it are single-quoted and must be doubled ('') to escape.
--       We treat _ . / - as separators so "block_has_port" -> "block","has","port".
-- ------------------------------------------------------------
DROP TRIGGER IF EXISTS doc_ai;
DROP TRIGGER IF EXISTS doc_ad;
DROP TRIGGER IF EXISTS doc_au;
DROP TABLE   IF EXISTS doc_fts;

CREATE VIRTUAL TABLE doc_fts USING fts5(
  title,
  ctx_hdr,
  body_text,
  content='doc', content_rowid='rowid',
  tokenize = 'unicode61 separators ''._/-'''
);

-- Keep FTS in sync with base table
CREATE TRIGGER doc_ai AFTER INSERT ON doc BEGIN
  INSERT INTO doc_fts(rowid, title, ctx_hdr, body_text)
  VALUES (new.rowid, new.title, new.ctx_hdr, new.body_text);
END;

CREATE TRIGGER doc_ad AFTER DELETE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, ctx_hdr, body_text)
  VALUES('delete', old.rowid, old.title, old.ctx_hdr, old.body_text);
END;

CREATE TRIGGER doc_au AFTER UPDATE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, ctx_hdr, body_text)
  VALUES('delete', old.rowid, old.title, old.ctx_hdr, old.body_text);
  INSERT INTO doc_fts(rowid, title, ctx_hdr, body_text)
  VALUES (new.rowid, new.title, new.ctx_hdr, new.body_text);
END;

-- ------------------------------------------------------------
-- Convenience view joining doc + fts with bm25 score
-- (You should still run MATCH against doc_fts in code.)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_search;
CREATE VIEW v_search AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  bm25(doc_fts) AS score
FROM doc AS d
JOIN doc_fts ON doc_fts.rowid = d.rowid;


-- ------------------------------------------------------------
-- Fallback views (score is NULL so UIs/tests can tell)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_summaries;
CREATE VIEW v_summaries AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  NULL        AS score,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d
WHERE d.doc_type = 'summary'
ORDER BY created_at DESC;

DROP VIEW IF EXISTS v_recent;
CREATE VIEW v_recent AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  NULL        AS score,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d
ORDER BY created_at DESC;

-- ------------------------------------------------------------
-- (Optional) Scoped doc view exposing created_at for convenience
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_doc_scoped;
CREATE VIEW v_doc_scoped AS
SELECT
  d.*,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d;
