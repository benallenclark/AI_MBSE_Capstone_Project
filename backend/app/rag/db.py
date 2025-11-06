# ------------------------------------------------------------
# Module: app/rag/db.py
# Purpose: Open a per-model RAG SQLite DB and expose task-style queries.
# ------------------------------------------------------------

from __future__ import annotations
import sqlite3, logging
from app.core.config import settings
from app.core import paths

log = logging.getLogger("rag.db")
DEFAULT_DB_PATH = str(settings.RAG_DB)

# Precondition: `scope` must include {"model_id","vendor","version"}; `limit` should be a positive int.
# Read-only query; no writes. Caller handles empty results as “no issues found”.
def missing_ports(scope: dict, limit: int = 200):
    
    # May raise FileNotFoundError if the RAG DB does not exist yet (pipeline not run).
    # If an exception occurs before `con.close()`, the connection may stay open—wrap in try/finally if you extend this.
    con = connect()
    
    # Ensures rows can be converted to `dict` without manual column indexing.
    con.row_factory = sqlite3.Row
    
    # Hard-codes probe_id/doc_type and expects `json_metadata` keys (subject_id, subject_name, has_issue).
    # If evidence schema changes, this view must be updated in lockstep.
    q = """
      SELECT d.doc_id,
             d.title,
             json_extract(d.json_metadata,'$.subject_id')   AS subject_id,
             json_extract(d.json_metadata,'$.subject_name') AS subject_name
      FROM doc d
      WHERE d.model_id=? AND d.vendor=? AND d.version=?
        AND d.probe_id='mml_2.block_has_port'
        AND d.doc_type='block'
        AND json_extract(d.json_metadata,'$.has_issue')=1
      ORDER BY subject_name
      LIMIT ?
    """
    rows = con.execute(q, (scope["model_id"], scope["vendor"], scope["version"], limit)).fetchall()
    con.close()
    
    # Returns a list of plain dicts suitable for JSON responses or templating.
    return [dict(r) for r in rows]


def connect() -> sqlite3.Connection:
  
  # Centralized DB location from app.core.paths; do not hardcode elsewhere to avoid drift.
    p = paths.RAG_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    
    # Fails fast with a clear message if the DB hasn’t been bootstrapped (pipeline step 3).
    # Side effect: logs an error and raises FileNotFoundError for callers to handle.
    if not p.exists():
        msg = f"RAG DB not found at {p}. Run pipeline step 3 to create it."
        log.error(msg)
        raise FileNotFoundError(msg)
    con = sqlite3.connect(p.as_posix())
    
    # All callers of `connect()` get Row objects by default; consistent with `missing_ports`.
    con.row_factory = sqlite3.Row
    return con
