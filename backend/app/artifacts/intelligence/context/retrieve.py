# ------------------------------------------------------------
# Module: app/artifacts/intelligence/context/retrieve.py
# Purpose: Run the retrieval pipeline (BM25 → summaries → recent) with self-heal.
# ------------------------------------------------------------

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.infra.core import paths  # <- to load schema.sql for self-heal

from ...rag.diagnostics import db_path
from ...rag.query_normalizer import build_match

log = logging.getLogger(__name__)

# ---------- Self-heal helpers ----------


def _ensure_views(con: sqlite3.Connection) -> None:
    """Idempotently create/refresh views by executing the packaged schema."""
    sql = paths.schema_sql_text()  # includes v_search, v_summaries, v_recent
    con.executescript(sql)


def _is_missing_view(err: Exception) -> bool:
    """Return True if the OperationalError is due to missing v_* objects/columns."""
    msg = str(err).lower()
    return any(
        s in msg
        for s in (
            "no such table: v_",
            "no such view: v_",
            "no such column: score",  # fallbacks include score
            "no such column: created_at",  # v_recent/v_summaries expose created_at
        )
    )


def _run(con: sqlite3.Connection, sql: str, params: tuple, *, retry: bool = True):
    """Execute a SELECT and fetchall(); on missing view/columns, self-heal once."""
    try:
        return con.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        if retry and _is_missing_view(e):
            log.info("rag.retrieve.self_heal start")
            _ensure_views(con)
            log.info("rag.retrieve.self_heal done")
            return _run(con, sql, params, retry=False)
        raise


# ---------- Public API ----------


def retrieve(question: str, scope: dict[str, Any], k: int = 8) -> list[dict]:
    """Return top-k rows from rag.sqlite using FTS5 BM25; fallback to summaries/recent.

    Self-heals once if v_search/v_summaries/v_recent aren’t present by executing schema.sql.
    """
    model_id = (scope or {}).get("model_id")
    if not model_id:
        # when scope is empty, caller expects global-ish probe (recent/summaries)
        pass

    path = db_path(model_id)
    con = sqlite3.connect(path)
    log.info("rag.retrieve.open path=%s", path)

    con.row_factory = sqlite3.Row

    rows: list[sqlite3.Row] = []
    src = "fts"

    with con:
        match = build_match(question)
        log.debug("rag.retrieve.match=%s", match[:120])

        rows = []
        if match:
            # Try weighted BM25 first (title > ctx_hdr > body_text).
            sql_weighted = (
                "SELECT d.doc_id, d.title, d.body_text AS body, "
                "       bm25(doc_fts, 5.0, 2.0, 1.0) AS score "
                "FROM doc AS d "
                "JOIN doc_fts ON doc_fts.rowid = d.rowid "
                "WHERE doc_fts MATCH ? "
                # This only gets the summary evidence
                "  AND d.doc_type = 'summary' "
                "ORDER BY score DESC "
                "LIMIT ?"
            )
            # Fallback to unweighted BM25 if schema/column count differs.
            sql_unweighted = (
                "SELECT d.doc_id, d.title, d.body_text AS body, "
                "       bm25(doc_fts) AS score "
                "FROM doc AS d "
                "JOIN doc_fts ON doc_fts.rowid = d.rowid "
                "WHERE doc_fts MATCH ? "
                # This only gets the summary evidence
                "  AND d.doc_type = 'summary' "
                "ORDER BY score DESC "
                "LIMIT ?"
            )
            try:
                rows = _run(con, sql_weighted, (match, k))
                fts_count = len(rows)
                log.debug("rag.retrieve.fts_hits=%d match=%r", fts_count, match)
            except sqlite3.OperationalError as e:
                log.debug("weighted bm25 failed (%s); trying unweighted", e)
                try:
                    rows = _run(con, sql_unweighted, (match, k))
                except sqlite3.OperationalError as e2:
                    log.warning("FTS query failed; will fallback: %s", e2)
                    rows = []

        if not rows:
            src = "v_summaries"
            rows = _run(
                con,
                "SELECT doc_id, title, body, NULL AS score "
                "FROM v_summaries ORDER BY created_at DESC LIMIT ?",
                (k,),
            )

        if not rows:
            src = "v_recent"
            rows = _run(
                con,
                "SELECT doc_id, title, body, NULL AS score "
                "FROM v_recent ORDER BY created_at DESC LIMIT ?",
                (k,),
            )

    log.debug("rag.retrieve.source=%s hits=%d", src, len(rows))
    out = [dict(r) for r in rows]
    for o in out:
        o.setdefault("_src", src)
    return out
