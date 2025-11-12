# ------------------------------------------------------------
# Module: app/rag/retrieve.py
# Purpose: Retrieve top-k evidence docs via FTS5 BM25 with scoped fallbacks.
# ------------------------------------------------------------

"""Query per-model RAG SQLite indexes using FTS5 with sensible fallbacks.

This module provides a small retrieval pipeline:
1) Try BM25 (FTS5) keyword search built from a normalized question.
2) If empty, return recent summaries.
3) If still empty, return recent in-scope docs.

Responsibilities
----------------
- Normalize natural-language questions into compact FTS5 MATCH strings.
- Run scoped (model_id/vendor/version) queries against `doc`/`doc_fts`.
- Prefer relevance via bm25, then fall back to summaries or recency.
- Log scope counts, query passes used, and basic timing details.
"""

import logging
import re
import sqlite3
import time
from typing import Any

from app.artifacts.rag.db import connect
from app.infra.core.config import settings

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


def _build_match(q: str) -> str:
    """Turn a free-text question into a compact FTS5 MATCH query string.

    Notes
    -----
    - Lowercases, removes stopwords, keeps up to 8 tokens.
    - Adds a trailing `*` for tokens with length ≥ 5 (prefix search).
    - Special-cases the phrase `"missing ports"` when both terms are present.
    - Returns an empty string when nothing useful is extracted (signals fallback).
    """
    toks = [t for t in _token_re.findall(q.lower()) if t not in _STOP]
    if not toks:
        return ""
    stems = []
    for t in toks[:8]:
        stems.append(f"{t}*" if len(t) >= 5 else t)
    phrase = '"missing ports" OR ' if ("missing" in toks and "ports" in toks) else ""
    return f"{phrase}" + " OR ".join(stems)


def _db_path(con: sqlite3.Connection) -> str:
    """Best-effort to report the on-disk path of the main DB (for logging)."""
    try:
        # PRAGMA database_list: (seq, name, file)
        row = next(con.execute("PRAGMA database_list"), None)
        if row and len(row) >= 3:
            return row[2] or ":memory:"
    except Exception:
        pass
    return "unknown"


def retrieve(
    question: str, scope: dict[str, str], k: int | None = None
) -> list[dict[str, Any]]:
    """Return up to k scoped evidence docs using FTS5 bm25 with fallbacks.

    Search Order
    ------------
    1) BM25 keyword search using a normalized MATCH string.
    2) Recent summaries in scope (`doc_type='summary'`).
    3) Most recent docs in scope (insert order via rowid).

    Parameters
    ----------
    question : str
        Natural-language question to search with.
    scope : dict[str, str]
        Must include `model_id`, `vendor`, `version`.
    k : int | None
        Max rows to return; defaults to `settings.RAG_TOP_K`.

    Returns
    -------
    list[dict[str, Any]]
        List of doc rows as plain dicts.

    Notes
    -----
    - Read-only; never writes.
    - Raises `FileNotFoundError` if the per-model DB is missing (via `connect()`).
    - Requires `doc` and `doc_fts` with rowid parity (FTS5 shadow table).
    """
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

    # Recency = insert order only (no timestamps by design).
    order_recent = "d.rowid DESC"

    # Log begin with scope + db path (no full question to avoid noise).
    # Always inline key fields in the message so they survive any formatter.
    logger.info(
        f"version={scope.get('version')} k={k} q_len={len(question or '')} db={db_path}"
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

    # Pass 2: summaries (prefer rowid)
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
