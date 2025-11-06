# ------------------------------------------------------------
# Module: app/rag/retrieve.py
# Purpose: Retrieve top-k evidence docs via FTS5 BM25 with scoped fallbacks.
# ------------------------------------------------------------

import re, sqlite3
from typing import List, Dict, Any
from app.rag.db import connect
from app.core.config import settings

# --- tiny normalizer to make FTS5 match useful on natural language questions ---
_STOP = {
    "a","an","the","and","or","but","if","then","else","of","for","to","in","on","at",
    "is","are","was","were","be","been","being","do","does","did","doing",
    "what","which","who","whom","whose","why","how","should","would","could","can",
    "we","you","i"
}
_token_re = re.compile(r"[a-z0-9_]+")

# Uses PRAGMA table_info; intended for constant table/column names.
# Do not pass untrusted identifiers here—identifiers aren’t parameterized.
def _has_column(con: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))

# Lowercases, drops stopwords, limits to 8 tokens; words ≥5 chars get a trailing `*` for prefix search.
# Returns "" for unusable queries so we fall back to summaries/recent docs.
def _build_match(q: str) -> str:
    toks = [t for t in _token_re.findall(q.lower()) if t not in _STOP]
    if not toks:
        return ""
    stems = []
    for t in toks[:8]:
        stems.append(f"{t}*" if len(t) >= 5 else t)
    phrase = '"missing ports" OR ' if ("missing" in toks and "ports" in toks) else ""
    return f"{phrase}" + " OR ".join(stems)

# Precondition: `scope` must include {"model_id","vendor","version"}; will KeyError if missing.
# Returns a list of dict rows; pure read-only behavior (no writes).
def retrieve(question: str, scope: Dict[str, str], k: int | None = None) -> List[Dict[str, Any]]:
    
    # May raise if the RAG DB is missing; callers should handle FileNotFoundError from connect().
    # Early returns close the connection, but exceptions before `.close()` will leak it—add try/finally if you extend logic.
    con = connect()
    
    # Falls back to a configured default. Ensure `k > 0` upstream—SQLite `LIMIT 0` returns nothing.
    k = k or settings.RAG_TOP_K
    
    con.row_factory = sqlite3.Row

    # Prefers event timestamps when available; otherwise uses insertion order via rowid.
    # Be aware: rowid tracks insert sequence, not document time.
    has_ts = _has_column(con, "doc", "ts_ms")
    order_recent = "d.ts_ms DESC" if has_ts else "d.rowid DESC"  # fallback if ts_ms absent
    
    # Requires `doc` and `doc_fts` with `rowid` parity (FTS5 shadow table). If FTS wasn’t bootstrapped, this will error.
    # Filters strictly by (model_id, vendor, version) to keep retrieval in-scope.
    base_sql = """
      SELECT d.doc_id, d.title, d.body_text, d.probe_id, d.doc_type, d.subject_type, d.subject_id
      FROM doc d
      JOIN doc_fts f ON f.rowid = d.rowid
      WHERE d.model_id = ? AND d.vendor = ? AND d.version = ?
    """
    base_params = [scope["model_id"], scope["vendor"], scope["version"]]

    # Pass 1: BM25 keyword search (only if we have a useful query)
    match = _build_match(question)
    if match:
        # MATCH uses a bound parameter—do not interpolate the MATCH string directly.
        # `bm25(...) ASC` ranks best matches first; ensure the FTS table uses the default BM25 config.
        q1 = base_sql + " AND doc_fts MATCH ? ORDER BY bm25(doc_fts) ASC LIMIT ?"
        rows = con.execute(q1, (*base_params, match, k)).fetchall()
        if rows:
            con.close()
            return [dict(r) for r in rows]

    # Pass 2: summaries (prefer recency if ts_ms exists; else rowid)
    q2 = base_sql + f" AND d.doc_type = 'summary' ORDER BY {order_recent} LIMIT ?"
    rows = con.execute(q2, (*base_params, k)).fetchall()
    if rows:
        con.close()
        return [dict(r) for r in rows]

    # Pass 3: anything recent in-scope (same dynamic ordering)
    q3 = base_sql + f" ORDER BY {order_recent} LIMIT ?"
    rows = con.execute(q3, (*base_params, k)).fetchall()
    con.close()
    return [dict(r) for r in rows]
