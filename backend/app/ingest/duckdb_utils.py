# ------------------------------------------------------------
# Module: backend/app/ingest/duckdb_utils.py
# Purpose: Utility helpers for DuckDB data import and view management.
# ------------------------------------------------------------

"""DuckDB utilities for JSONL-to-Parquet conversion, view creation, and row counting.

This module provides lightweight helpers to perform file-based data operations
using DuckDB, ensuring correct SQL literal escaping and quoting.

Responsibilities
----------------
- Safely quote SQL identifiers for DuckDB commands.
- Copy JSONL data to Parquet format with compression via DuckDB.
- Create or replace a DuckDB view referencing a Parquet file.
- Count the number of rows in a DuckDB table or view.
"""

from __future__ import annotations

import duckdb


def _qi(name: str) -> str:
    """Quote an identifier for DuckDB, escaping internal quotes."""
    return '"' + name.replace('"', '""') + '"'


def copy_jsonl_to_parquet(
    con: duckdb.DuckDBPyConnection,
    json_path_sql_literal: str,
    pq_path_sql_literal: str,
) -> None:
    """Copy JSONL → Parquet using DuckDB.

    Inputs must already be SQL-literal-safe paths (single quotes escaped);
    callers should pass `.as_posix().replace("'", "''")`.
    """
    con.execute(
        f"""
        COPY (
            SELECT * FROM read_json_auto('{json_path_sql_literal}', union_by_name = true)
        ) TO '{pq_path_sql_literal}' (FORMAT PARQUET, COMPRESSION 'zstd');
        """
    )


def create_or_replace_view(
    con: duckdb.DuckDBPyConnection, table: str, pq_path_sql_literal: str
) -> None:
    """Create or replace a view selecting from a Parquet file."""
    con.execute(
        f"CREATE OR REPLACE VIEW {_qi(table)} AS SELECT * FROM read_parquet('{pq_path_sql_literal}')"
    )


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    """Return the total number of rows in a DuckDB table or view."""
    return int(con.execute(f"SELECT COUNT(*) FROM {_qi(table)};").fetchone()[0])
