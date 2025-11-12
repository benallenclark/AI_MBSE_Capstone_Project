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
    """Open a DuckDB connection with tuned PRAGMAs for performance.

    Notes
    -----
    - Applies `threads`, `memory_limit`, and `enable_object_cache` settings.
    - Fails gracefully if PRAGMA statements are not supported or error.
    - Callers must close the returned connection when done.
    """
    try:
        # Try to open a connection to the specified DuckDB database file.
        con = duckdb.connect(str(db_path))
    except Exception as e:  # pragma: no cover
        # Wrap low-level DuckDB errors with a custom error for clearer logs.
        raise DuckDBError(f"duckdb connect failed db='{db_path}'") from e
    try:
        # Apply connection-level PRAGMAs for predictable performance.
        con.execute(f"PRAGMA threads={int(threads)}")
        con.execute(f"PRAGMA memory_limit='{mem}'")
        con.execute("PRAGMA enable_object_cache=true")
    except Exception:
        # If any PRAGMA fails, keep the connection open with defaults.
        # This prevents production crashes due to platform/version differences.
        pass
    return con
