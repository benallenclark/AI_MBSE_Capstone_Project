# ------------------------------------------------------------
# Module: app/criteria/mml_1/predicate_count_tables.py
# Purpose: Verify existence and population of core MBSE tables (MML-1).
# ------------------------------------------------------------

"""MML-1 Predicate: Count presence and population of core MBSE tables.

Summary:
    Baseline health check that the parsed SysML/MBSE model materialized into a
    valid, queryable SQLite schema. Confirms existence and non-empty population
    of expected `t_*` tables.

Behavior:
    - Enumerates expected core tables (`_TABLES`).
    - Checks which expected tables exist.
    - Counts rows per expected table.
    - Reports unexpected user tables for visibility.
    - Returns evidence for dashboards/reports.

Developer Notes:
    - Keep lightweight and adapter-agnostic.
    - Extend `_TABLES` only for entities standard across all models.
    - Always returns True if the schema can be inspected.
"""

from typing import Tuple, Dict, Any, TypedDict, Iterable, List
from app.criteria.protocols import Context, DbLike
import logging

__all__ = ("PREDICATE_ID", "evaluate")

PREDICATE_ID = "count_tables"
log = logging.getLogger("mml_1.count_tables")

# Freeze for integrity; keep names stable across runs
_TABLES = frozenset({
    "t_package", "t_object", "t_objectconstraint", "t_objectproperties",
    "t_attribute", "t_attributetag", "t_operation", "t_operationparams",
    "t_connector", "t_connectortag", "t_diagram", "t_diagramobjects",
    "t_diagramlinks", "t_taggedvalue", "t_xref",
})
TABLES_SORTED: tuple[str, ...] = tuple(sorted(_TABLES))

class TableRec(TypedDict):
    table: str
    rows: int

class Details(TypedDict):
    capabilities: Dict[str, bool]
    vendor: str
    version: str
    missing_tables: List[str]
    unexpected_tables: List[str]
    table_counts: Dict[str, bool]
    row_counts: Dict[str, int]
    total_rows: int
    counts: Dict[str, int]                 # {"passed": X, "failed": Y, "missing": Z, "unexpected": W}
    evidence: Dict[str, List[TableRec]]    # {"passed": [...], "failed": [...]}

def _sorted(iterable: Iterable[str]) -> List[str]:
    return sorted(iterable)

def evaluate(db: DbLike, ctx: Context) -> Tuple[bool, Dict[str, Any]]:
    # Early guard allows future config where _TABLES may be empty.
    if not _TABLES:
        details: Details = {
            "capabilities": {"counts": True, "sql": True, "per_table": True},
            "vendor": getattr(ctx, "vendor", ""),
            "version": getattr(ctx, "version", ""),
            "missing_tables": [],
            "unexpected_tables": [],
            "table_counts": {},
            "row_counts": {},
            "total_rows": 0,
            "counts": {"passed": 0, "failed": 0, "missing": 0, "unexpected": 0},
            "evidence": {"passed": [], "failed": []},
        }
        return True, dict(details)

    vendor = getattr(ctx, "vendor", "")
    version = getattr(ctx, "version", "")

    # Presence of expected tables
    placeholders = ",".join(["?"] * len(_TABLES))
    q_expected = f"SELECT name FROM sqlite_schema WHERE type='table' AND name IN ({placeholders})"
    expected_present = {row[0] for row in db.execute(q_expected, tuple(_TABLES)).fetchall()}

    # All non-internal tables (for unexpected visibility)
    q_all = "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    all_present = {row[0] for row in db.execute(q_all).fetchall()}
    unexpected = all_present.difference(_TABLES)

    # Row counts (deterministic order)
    row_counts: Dict[str, int] = {}
    total_rows = 0
    for t in TABLES_SORTED:
        n = int(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]) if t in expected_present else 0
        row_counts[t] = n
        total_rows += n

    # Present & non-empty flags
    table_counts: Dict[str, bool] = {t: (row_counts[t] > 0) for t in TABLES_SORTED}

    # Evidence partition for expected tables only
    passed_list: List[TableRec] = []
    failed_list: List[TableRec] = []
    for t in TABLES_SORTED:
        if t in expected_present:
            rec: TableRec = {"table": t, "rows": row_counts[t]}
            (passed_list if row_counts[t] > 0 else failed_list).append(rec)

    missing_list = _sorted(_TABLES.difference(expected_present))
    unexpected_list = _sorted(unexpected)

    details: Details = {
        "capabilities": {"counts": True, "sql": True, "per_table": True},
        "vendor": vendor,
        "version": version,
        "missing_tables": missing_list,
        "unexpected_tables": unexpected_list,
        "table_counts": {k: table_counts[k] for k in TABLES_SORTED},
        "row_counts": {k: row_counts[k] for k in TABLES_SORTED},
        "total_rows": total_rows,
        "counts": {
            "passed": len(passed_list),
            "failed": len(failed_list),
            "missing": len(missing_list),
            "unexpected": len(unexpected_list),
        },
        "evidence": {"passed": passed_list, "failed": failed_list},
    }
    # Pass if the schema was inspectable.
    return True, dict(details)
