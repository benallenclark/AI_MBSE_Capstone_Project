# ------------------------------------------------------------
# Module: app/artifacts/rag/db.py
# Purpose: Open a per-model RAG SQLite DB and expose task-style queries.
# ------------------------------------------------------------

"""Helpers to locate and open a per-model RAG SQLite database.

This module centralizes path resolution for the models directory and provides
read-only query helpers (task-style) against the per-model `rag.sqlite`.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.infra.core import paths
from app.infra.core.config import settings

log = logging.getLogger("rag.db")


def _resolve_models_dir() -> Path:
    """Return the root directory that holds all model subfolders.

    Prefers an explicit Path on `app.core.paths`, then `settings`, then a
    conservative literal. This does not create directories or files.
    """
    # Prefer an explicit Path on `paths`, then `settings`, then final safe literal.
    base = (
        getattr(paths, "MODELS_DIR", None)
        or getattr(settings, "MODELS_DIR", None)
        or "backend/data/models"
    )
    return Path(base)


def _rag_db_path_for(model_id: str) -> Path:
    """Compute the path to `<models_dir>/<model_id>/rag.sqlite` without creating it."""
    return _resolve_models_dir() / model_id / "rag.sqlite"


def connect(scope: dict) -> sqlite3.Connection:
    """Open a connection to the per-model RAG SQLite DB.

    Preconditions
    -------------
    - `scope` contains `model_id`, `vendor`, `version` (vendor/version are validated by callers/queries).
    - The per-model DB already exists (created by the ingest pipeline).

    Raises
    ------
    ValueError
        If required scope keys are missing.
    FileNotFoundError
        If the per-model DB file is absent.
    """
    missing = [k for k in ("model_id", "vendor", "version") if k not in (scope or {})]
    if missing:
        raise ValueError(f"RAG scope is missing required keys: {', '.join(missing)}")

    model_id = scope["model_id"]
    p = _rag_db_path_for(model_id)
    # Do NOT create directories/files here; if it doesn't exist, the pipeline hasn't produced it yet.
    if not p.exists():
        msg = (
            f"Per-model RAG DB not found for model_id='{model_id}' at {p}. "
            f"Run pipeline step 3 to create it."
        )
        log.error(msg)
        raise FileNotFoundError(msg)

    con = sqlite3.connect(p.as_posix())
    log.info("rag.db.open", extra={"path": p.as_posix(), "model_id": model_id})

    # All callers of `connect()` get Row objects by default; consistent with `missing_ports`.
    con.row_factory = sqlite3.Row
    return con
