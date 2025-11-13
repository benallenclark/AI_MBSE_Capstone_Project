# ------------------------------------------------------------
# Module: app/artifacts/rag/retrieve.py
# Purpose: Run the retrieval pipeline (BM25 → summaries → recent) with self-heal.
# ------------------------------------------------------------

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.infra.core import paths  # <- to load schema.sql for self-heal

from .diagnostics import db_path
from .query_normalizer import build_match

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
    with con:
        # 1) BM25 on normalized MATCH (uses v_search)
        match = build_match(question)
        log.debug("rag.retrieve.match=%s", build_match(question)[:120])
        try:
            rows = _run(
                con,
                "SELECT doc_id, title, body, score "
                "FROM v_search "
                "WHERE v_search MATCH ? "
                "ORDER BY score ASC "  # v_search already computes bm25(f) AS score
                "LIMIT ?",
                (match, k),
            )
        except sqlite3.OperationalError:
            # If FTS fails for other reasons, fall back below.
            rows = []

        if not rows:
            # 2) summaries fallback
            rows = _run(
                con,
                "SELECT doc_id, title, body, score "
                "FROM v_summaries "
                "ORDER BY created_at DESC "
                "LIMIT ?",
                (k,),
            )

        if not rows:
            # 3) recent fallback
            rows = _run(
                con,
                "SELECT doc_id, title, body, score "
                "FROM v_recent "
                "ORDER BY created_at DESC "
                "LIMIT ?",
                (k,),
            )

    return [dict(r) for r in rows]
