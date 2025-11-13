-- rag.sqlite
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS doc (
  doc_id TEXT PRIMARY KEY,                -- e.g. "14b92d4a/mml_2.block_has_port/block/425"
  model_id TEXT,
  vendor TEXT,
  version TEXT,
  mml INTEGER,
  probe_id TEXT,                          -- normalized: "mml_2.block_has_port"
  doc_type TEXT,                          -- "summary" | "block" | "entity" | ...
  subject_type TEXT,                      -- "block" | "port" | ...
  subject_id TEXT,
  title TEXT,
  ctx_hdr TEXT,
  body_text TEXT,
  json_metadata TEXT,
  ts_ms INTEGER
);

-- FTS5 over the searchable text; content=doc connects it to the base table.
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts
USING fts5(title, ctx_hdr, body_text, content='doc', content_rowid='rowid');

-- Keep FTS in sync
CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON doc BEGIN
  INSERT INTO doc_fts(rowid, title, ctx_hdr, body_text)
  VALUES (new.rowid, new.title, new.ctx_hdr, new.body_text);
END;
CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, ctx_hdr, body_text)
  VALUES('delete', old.rowid, old.title, old.ctx_hdr, old.body_text);
END;
CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, ctx_hdr, body_text)
  VALUES('delete', old.rowid, old.title, old.ctx_hdr, old.body_text);
  INSERT INTO doc_fts(rowid, title, ctx_hdr, body_text)
  VALUES (new.rowid, new.title, new.ctx_hdr, new.body_text);
END;

-- --------------------------------------------
-- Read-friendly views used by retrieval
-- --------------------------------------------

-- FTS join view with a bm25 score (lower is better)
DROP VIEW IF EXISTS v_search;
CREATE VIEW v_search AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  bm25(f)      AS score
FROM doc d
JOIN doc_fts f ON f.rowid = d.rowid;

-- Most recent summaries first; provide a score column for shape stability
DROP VIEW IF EXISTS v_summaries;
CREATE VIEW v_summaries AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  0.0         AS score,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d
WHERE d.doc_type = 'summary'
ORDER BY created_at DESC;

-- Most recent documents in scope (any type)
DROP VIEW IF EXISTS v_recent;
CREATE VIEW v_recent AS
SELECT
  d.doc_id,
  d.title,
  d.body_text AS body,
  0.0         AS score,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d
ORDER BY created_at DESC;

-- (Optional but recommended) Scope filters to avoid repeating WHERE clauses
DROP VIEW IF EXISTS v_doc_scoped;
CREATE VIEW v_doc_scoped AS
SELECT
  d.*,
  COALESCE(d.ts_ms, d.rowid) AS created_at
FROM doc d;
