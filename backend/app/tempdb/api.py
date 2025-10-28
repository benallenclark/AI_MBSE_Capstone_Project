# ------------------------------------------------------------
# Module: app/tempdb/api.py
# Purpose: Provide thin, vendor-agnostic helpers for in-memory SQLite operations.
# ------------------------------------------------------------


"""Thin convenience API over sqlite3 for temp DB operations.

Summary:
    Helper functions to run queries and scripts on the in-memory SQLite
    databases produced by the XML loader and adapters.

Details:
    - `query_all` returns rows as dictionaries keyed by column name.
    - `exec_script` executes multi-statement SQL scripts (DDL/DML).
    - `executemany` performs bulk parameterized inserts/updates.

Developer Guidance:
    Keep this module minimal and vendor-agnostic. Prefer parameterized SQL and
    avoid string interpolation to prevent SQL issues.
"""

import sqlite3
from typing import Iterable, Any


def query_all(db: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Execute a SELECT and return all rows as dictionaries.

    Args:
        db: Live SQLite connection (typically in-memory).
        sql: Parameterized SELECT statement.
        params: Iterable of parameters bound to the SQL.

    Returns:
        list[dict[str, Any]]: Result set with column-name keys.

    Example:
        >>> rows = query_all(db, "SELECT name FROM sqlite_schema WHERE type=?", ["table"])
        >>> rows[:1]
        [{'name': 't_object'}]
    """
    cur = db.execute(sql, tuple(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def exec_script(db: sqlite3.Connection, script: str) -> None:
    """Execute a multi-statement SQL script (DDL/DML).

    Args:
        db: Live SQLite connection.
        script: One or more SQL statements separated by semicolons.

    Returns:
        None

    Example:
        >>> exec_script(db, "CREATE TABLE x(id INTEGER); INSERT INTO x VALUES (1);")
    """
    db.executescript(script)


def executemany(db: sqlite3.Connection, sql: str, rows: list[tuple]) -> None:
    """Execute a parameterized statement for many rows.

    Args:
        db: Live SQLite connection.
        sql: SQL statement with positional placeholders (e.g., `INSERT INTO t(a,b) VALUES (?, ?)`).
        rows: List of tuples matching the placeholders.

    Returns:
        None

    Example:
        >>> executemany(db, "INSERT INTO t_object(name) VALUES (?)", [("A",), ("B",)])
    """
    db.executemany(sql, rows)
