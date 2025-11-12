# ------------------------------------------------------------
# Module: backend/app/ingest/duckdb_connection.py
# Purpose: Open and configure a DuckDB connection with sensible defaults.
# ------------------------------------------------------------

"""Establish a DuckDB connection with basic configuration and safety handling.

This module provides a helper to open a DuckDB database and apply key PRAGMAs
for performance and stability, while gracefully handling connection errors.

Responsibilities
----------------
- Open a DuckDB connection from a given file path.
- Apply thread and memory PRAGMAs for controlled resource usage.
- Enable the DuckDB object cache for improved performance.
- Handle connection or PRAGMA errors with safe fallbacks.
"""

from pathlib import Path

import duckdb

from .errors import DuckDBError


def open_duckdb(db_path: Path, threads: int, mem: str) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with basic PRAGMAs applied."""
    try:
        con = duckdb.connect(str(db_path))
    except Exception as e:  # pragma: no cover
        raise DuckDBError(f"duckdb connect failed db='{db_path}'") from e
    try:
        con.execute(f"PRAGMA threads={int(threads)}")
        con.execute(f"PRAGMA memory_limit='{mem}'")
        con.execute("PRAGMA enable_object_cache=true")
    except Exception:
        # Continue with defaults if PRAGMAs fail (avoid crashing production)
        pass
    return con
