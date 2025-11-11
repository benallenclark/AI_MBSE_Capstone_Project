# ------------------------------------------------------------
# Module: app/rag/retrieve.py
# Purpose: Retrieve top-k evidence docs via FTS5 BM25 with scoped fallbacks.
# ------------------------------------------------------------

import logging
import re
import sqlite3
import time
from typing import Any

from app.core.config import settings
from app.rag.db import connect

logger = logging.getLogger(__name__)

# --- tiny normalizer to make FTS5 match useful on natural language questions ---
_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "doing",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "why",
    "how",
    "should",
    "would",
    "could",
    "can",
    "we",
    "you",
    "i",
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


def _db_path(con: sqlite3.Connection) -> str:
    """Best-effort to report the on-disk path of the main DB."""
    try:
        # PRAGMA database_list: (seq, name, file)
        row = next(con.execute("PRAGMA database_list"), None)
        if row and len(row) >= 3:
            return row[2] or ":memory:"
    except Exception:
        pass
    return "unknown"


# Precondition: `scope` must include {"model_id","vendor","version"}; will KeyError if missing.
# Returns a list of dict rows; pure read-only behavior (no writes).
def retrieve(
    question: str, scope: dict[str, str], k: int | None = None
) -> list[dict[str, Any]]:
    t0 = time.perf_counter()
    # Open the per-model DB; raises FileNotFoundError if the model's rag.sqlite doesn't exist yet.
    con = connect(scope)
    # From here on, ensure we close the connection on all paths.
    pass_used = "none"
    rows: list[sqlite3.Row] = []
    match: str = ""
    # Capture DB path early for diagnostics.
    db_path = _db_path(con)

    # Falls back to a configured default. Ensure `k > 0` upstream—SQLite `LIMIT 0` returns nothing.
    k = k or settings.RAG_TOP_K

    con.row_factory = sqlite3.Row

    # Prefers event timestamps when available; otherwise uses insertion order via rowid.
    # Be aware: rowid tracks insert sequence, not document time.
    try:
        has_ts = _has_column(con, "doc", "ts_ms")
    except Exception:
        logger.exception("rag.retrieve.schema_check_failed")
        con.close()
        raise
    order_recent = (
        "d.ts_ms DESC" if has_ts else "d.rowid DESC"
    )  # fallback if ts_ms absent
    # Log begin with scope + db path (no full question to avoid noise).
    # Always inline key fields in the message so they survive any formatter.
    logger.info(
        f"rag.retrieve.start model_id={scope.get('model_id')} vendor={scope.get('vendor')} "
        f"version={scope.get('version')} k={k} q_len={len(question or '')} db={db_path} has_ts={int(bool(has_ts))}"
    )

    # Quick scope sanity: do we have *any* docs for this (model_id, vendor, version)?
    try:
        scope_cnt = con.execute(
            "SELECT COUNT(*) FROM doc WHERE model_id=? AND vendor=? AND version=?",
            (scope["model_id"], scope["vendor"], scope["version"]),
        ).fetchone()[0]
        logger.info(f"rag.retrieve.scope_count count={scope_cnt}")
        if scope_cnt == 0:
            # Fail-fast hint: this is almost certainly a scope mismatch or DB routing issue.
            logger.warning(
                f"rag.retrieve.scope_empty model_id={scope['model_id']} vendor={scope['vendor']} "
                f"version={scope['version']} db={db_path}"
            )
    except Exception:
        logger.exception("rag.retrieve.scope_count.error")

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
    try:
        match = _build_match(question)
        if match:
            q1 = base_sql + " AND doc_fts MATCH ? ORDER BY bm25(doc_fts) ASC LIMIT ?"
            rows = con.execute(q1, (*base_params, match, k)).fetchall()
            logger.info(
                f"rag.retrieve.pass1 rows={len(rows)} match_preview={match[:120]}"
            )
            if rows:
                pass_used = "pass1_bm25"
                return [dict(r) for r in rows]
    except Exception:
        logger.exception(
            "rag.retrieve.pass1.error",
            extra={"match_preview": (match or "")[:120]},
        )
        con.close()
        raise

    # Pass 2: summaries (prefer recency if ts_ms exists; else rowid)
    try:
        q2 = base_sql + f" AND d.doc_type = 'summary' ORDER BY {order_recent} LIMIT ?"
        rows = con.execute(q2, (*base_params, k)).fetchall()
        logger.info(f"rag.retrieve.pass2_summaries rows={len(rows)}")
        if rows:
            pass_used = "pass2_summary"
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("rag.retrieve.pass2.error")
        con.close()
        raise

    # Pass 3: anything recent in-scope (same dynamic ordering)
    try:
        q3 = base_sql + f" ORDER BY {order_recent} LIMIT ?"
        rows = con.execute(q3, (*base_params, k)).fetchall()
        pass_used = "pass3_recent"
        logger.info(f"rag.retrieve.pass3_recent rows={len(rows)}")
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("rag.retrieve.pass3.error")
        raise
    finally:
        # Always log end + close connection
        try:
            logger.info(
                f"rag.retrieve.done pass={pass_used} retrieved={len(rows or [])} "
                f"dur_ms={int((time.perf_counter() - t0) * 1000)} db={db_path}"
            )
        finally:
            con.close()
