# ------------------------------------------------------------
# Module: app/criteria/mml_1/predicate_count_tables.py
# Purpose: Verify presence and population of core MBSE tables for MML-1 maturity.
# ------------------------------------------------------------

"""Predicate: Count presence and population of core MBSE tables (MML-1).

Summary:
    Serves as a foundational maturity check verifying that expected
    SysML/MBSE tables exist and contain rows. This confirms that the
    uploaded model has been successfully parsed and materialized into
    a usable in-memory database.

Details:
    - Runs introspection queries on the SQLite schema.
    - Counts both table existence and row population across key `t_*` tables.
    - Produces evidence used in reports and dashboards to validate parser success.
    - Always returns True (predicate passes if model can be inspected at all).

Developer Guidance:
    - This predicate belongs to MML-1 (Model Presence).
    - Future predicates build upon this check, assuming a valid schema exists.
    - Extend `_TABLES` only if new entity types become standard across models.
    - Keep queries lightweight; this predicate is often used as a health baseline.
    - Avoid model-specific logic—this check must remain universally applicable.
"""

from typing import Tuple, Dict, Any
from app.criteria.protocols import Context, DbLike

PREDICATE_ID = "count_tables"

# Core tables expected from MBSE model exports
_TABLES = {
    "t_package", "t_object", "t_objectconstraint", "t_objectproperties",
    "t_attribute", "t_attributetag", "t_operation", "t_operationparams",
    "t_connector", "t_connectortag", "t_diagram", "t_diagramobjects",
    "t_diagramlinks", "t_taggedvalue", "t_xref",
}


def evaluate(db: DbLike, ctx: Context) -> Tuple[bool, Dict[str, Any]]:
    """Evaluate whether expected tables exist and record row counts.

    Args:
        db: SQLite connection for the parsed model.
        ctx: Context containing vendor/version metadata (unused here).

    Returns:
        tuple[bool, dict[str, Any]]:
            - bool: Always True (predicate only collects info).
            - dict: Evidence payload with table presence and row statistics.

    Example:
        >>> ok, details = evaluate(db, ctx)
        >>> details["row_counts"]["t_object"]
        722
    """
    # Detect which tables exist
    cur = db.execute("SELECT name FROM sqlite_schema WHERE type='table'")
    existing = {row[0] for row in cur.fetchall()}

    # Binary table presence flags
    table_counts: Dict[str, int] = {t: (1 if t in existing else 0) for t in _TABLES}

    # Count rows in each known table
    row_counts: Dict[str, int] = {}
    total_rows = 0
    for t in _TABLES:
        if t in existing:
            n = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        else:
            n = 0
        n = int(n)
        row_counts[t] = n
        total_rows += n

    details: Dict[str, Any] = {
        "capabilities": {"counts": True, "sql": True},
        "table_counts": table_counts,
        "row_counts": row_counts,
        "total_rows": total_rows,
    }
    return True, details
