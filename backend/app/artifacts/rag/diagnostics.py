# ------------------------------------------------------------
# Module: app/artifacts/rag/diagnostics.py
# Purpose: Path/diagnostic helpers for RAG retrieval (no silent fallbacks).
# ------------------------------------------------------------

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.infra.core import paths


# Return <model_id>/rag.sqlite as a POSIX string; raise if missing model_id or file.
def db_path(model_id: str) -> str:
    if not model_id:
        raise ValueError("model_id is required to resolve rag.sqlite")
    p: Path = paths.rag_sqlite(model_id)
    if not p.exists():
        raise FileNotFoundError(
            f"rag.sqlite not found for model_id='{model_id}' at {p}. "
            "Run the pipeline to create it."
        )
    # POSIX path so it’s safe to embed in sqlite URI on Windows too
    return p.as_posix()


# Inspect an existing sqlite3.Connection and return its on-disk filename; raise if unknown.
def db_path_from_connection(con: sqlite3.Connection) -> str:
    try:
        row = con.execute("PRAGMA database_list").fetchone()
    except Exception as e:
        raise RuntimeError("failed to inspect sqlite connection") from e

    file = row[2] if row and len(row) >= 3 else None
    if not file or file.strip() in ("", ":memory:"):
        raise ValueError("connection has no on-disk filename (:memory: or unknown)")
    return file
