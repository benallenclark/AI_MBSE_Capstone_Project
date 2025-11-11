# ------------------------------------------------------------
# Module: app/rag/bootstrap_index.py
# Purpose: Build a per-model SQLite RAG index from evidence.jsonl (doc table + FTS).
# ------------------------------------------------------------

import json
import sqlite3
import sys
from pathlib import Path

from app.core import paths

# Requires argv[1] to be a path to evidence.jsonl; raises IndexError if missing.
# Validate the argument upstream or guard with a usage message for robustness.
jsonl_path = Path(sys.argv[1]).resolve()

# Assumes layout: .../<model_id>/evidence/evidence.jsonl → up two levels to `<model_id>`.
# Invariant: if the evidence file moves, this resolution breaks—keep directory structure stable.
model_dir = (
    jsonl_path.parent.parent
)  # .../<model_id>/evidence/evidence.jsonl -> .../<model_id>

sqlite_path = (model_dir / "rag.sqlite").resolve()
sqlite_path.parent.mkdir(parents=True, exist_ok=True)


def _is_sqlite_file(p: Path) -> bool:
    try:
        with p.open("rb") as fh:
            return fh.read(16) == b"SQLite format 3\x00"
    except FileNotFoundError:
        return False


# Defensive: deletes a bogus file sitting at rag.sqlite before creating the DB.
# Side effect: potential data loss if a non-SQLite file is present—ensure `model_dir` is correct.
if sqlite_path.exists() and not _is_sqlite_file(sqlite_path):
    sqlite_path.unlink()

con = sqlite3.connect(sqlite_path.as_posix())

# WAL improves concurrent read performance; good for later search.
# Combined with `synchronous=NORMAL`, writes are faster but slightly less durable on power loss.
con.execute("PRAGMA journal_mode=WAL;")
con.execute("PRAGMA synchronous=NORMAL;")

# Loads the canonical schema text (no path math). Expect DDL to be idempotent or use IF NOT EXISTS.
# Error surface: will raise if the schema text is invalid or incompatible with existing tables.
con.executescript(paths.schema_sql_text())

ins = con.cursor()

# Uses `INSERT OR REPLACE` keyed by `doc_id`—new rows with the same `doc_id` overwrite old ones.
# Ensure `doc_id` is stable per evidence card to avoid accidental churn.
insert_sql = """
INSERT OR REPLACE INTO doc
(doc_id, model_id, vendor, version, mml, probe_id, doc_type, subject_type, subject_id,
 title, ctx_hdr, body_text, json_metadata)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


# Single-pass generator over JSONL; memory efficient for large files.
# Expects each line to be a JSON object; blank lines are skipped.
def iter_rows():
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            s = line.strip()
            if not s:
                continue
            j = json.loads(s)
            md = j.get("metadata", {}) or {}
            yield (
                # If `doc_id` is missing, synthesize one from (model_id/probe_id/n).
                # Stable ordering matters for reproducibility.
                # Beware empty `model_id`/`probe_id`—you can end up with ambiguous IDs.
                j.get("doc_id")
                or f"{md.get('model_id', '')}/{j.get('probe_id', '')}/{n}",
                md.get("model_id"),
                md.get("vendor"),
                md.get("version"),
                j.get("mml"),
                j.get("probe_id"),
                j.get("doc_type") or "evidence",
                md.get("subject_type"),
                str(md.get("subject_id") or ""),
                j.get("title"),
                j.get("ctx_hdr", ""),
                j.get("body") or j.get("body_text", ""),
                json.dumps(md, ensure_ascii=False),
            )


# Streams rows into a single transaction; commit below makes it atomic.
# If the JSONL is massive, consider chunking and periodic commits to bound lock time.
ins.executemany(insert_sql, iter_rows())
con.commit()
print("Writing per-model RAG DB:", sqlite_path)
print("Docs:", con.execute("SELECT COUNT(*) FROM doc").fetchone()[0])
print("FTS:", con.execute("SELECT COUNT(*) FROM doc_fts").fetchone()[0])
con.close()
