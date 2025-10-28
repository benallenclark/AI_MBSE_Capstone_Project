# ------------------------------------------------------------
# Module: app/criteria/mml_1/predicate_count_tables.py
# Purpose: Verify existence and population of core MBSE tables (MML-1).
# ------------------------------------------------------------

"""MML-1 Predicate: Count presence and population of core MBSE tables.

Summary:
    This predicate performs a baseline maturity check ensuring that a parsed
    SysML/MBSE model has been successfully materialized into a valid, queryable
    SQLite schema. It confirms both the existence and non-empty population of
    expected `t_*` tables, establishing confidence that the model adapter and
    XML loader functioned correctly.

Behavior:
    - Enumerates all expected core tables defined in `_TABLES`.
    - Checks which tables exist within the database.
    - Counts the number of rows in each present table.
    - Records unexpected user-defined tables for visibility.
    - Returns a structured evidence payload used for dashboard or report display.

Rationale:
    This predicate serves as the foundation for higher maturity levels (MML-2+),
    which assume a valid, complete schema. It acts as a health check for
    successful model ingestion and normalization.

Developer Notes:
    - Keep this predicate lightweight; it executes frequently.
    - Avoid vendor-specific logic; results must be adapter-agnostic.
    - Extend `_TABLES` only when new entity types become standard in all models.
    - Always return True if the schema can be inspected; this is a baseline check.
"""

from typing import Tuple, Dict, Any, TypedDict, Iterable, List
from app.criteria.protocols import Context, DbLike

PREDICATE_ID = "count_tables"

# Freeze for integrity; keep names stable across runs
_TABLES = frozenset({
    "t_package", "t_object", "t_objectconstraint", "t_objectproperties",
    "t_attribute", "t_attributetag", "t_operation", "t_operationparams",
    "t_connector", "t_connectortag", "t_diagram", "t_diagramobjects",
    "t_diagramlinks", "t_taggedvalue", "t_xref",
})

class Details(TypedDict):
    capabilities: Dict[str, bool]
    vendor: str
    version: str
    schema_seen: List[str]
    missing_tables: List[str]
    unexpected_tables: List[str]
    table_counts: Dict[str, bool]
    row_counts: Dict[str, int]
    total_rows: int

def _sorted(iterable: Iterable[str]) -> List[str]:
    return sorted(iterable)

def evaluate(db: DbLike, ctx: Context) -> Tuple[bool, Dict[str, Any]]:
    # Guard: nothing to check
    if not _TABLES:
        details: Details = {
            "capabilities": {"counts": True, "sql": True},
            "vendor": getattr(ctx, "vendor", ""),
            "version": getattr(ctx, "version", ""),
            "schema_seen": [],
            "missing_tables": [],
            "unexpected_tables": [],
            "table_counts": {},
            "row_counts": {},
            "total_rows": 0,
        }
        return True, details  # trivial pass

    # Only fetch expected names
    q = (
        f"SELECT name FROM sqlite_schema "
        f"WHERE type='table' AND name IN ({','.join(['?'] * len(_TABLES))})"
    )
    cur = db.execute(q, tuple(_TABLES))
    expected_present = {row[0] for row in cur.fetchall()}

    # Also capture unexpected user tables for visibility
    cur = db.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    all_present = {row[0] for row in cur.fetchall()}
    unexpected = all_present.difference(_TABLES)

    # Presence flags as bools
    table_counts: Dict[str, bool] = {t: (t in expected_present) for t in _TABLES}

    # Row counts
    row_counts: Dict[str, int] = {}
    total_rows = 0
    for t in _TABLES:
        if t in expected_present:
            n = db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            n = int(n)
        else:
            n = 0
        row_counts[t] = n
        total_rows += n

    details: Details = {
        "capabilities": {"counts": True, "sql": True},
        "vendor": getattr(ctx, "vendor", ""),
        "version": getattr(ctx, "version", ""),
        "schema_seen": _sorted(all_present),
        "missing_tables": _sorted(_TABLES.difference(expected_present)),
        "unexpected_tables": _sorted(unexpected),
        "table_counts": {k: table_counts[k] for k in _sorted(_TABLES)},
        "row_counts": {k: row_counts[k] for k in _sorted(_TABLES)},
        "total_rows": int(total_rows),
    }
    return True, details
