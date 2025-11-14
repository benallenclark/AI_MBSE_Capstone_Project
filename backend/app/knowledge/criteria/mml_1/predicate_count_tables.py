# ------------------------------------------------------------
# Module: app/knowledge/criteria/mml_1/predicate_count_tables.py
# Purpose: MML-1 "is the model parsable?" — required core tables exist & have rows
# Evidence v2: predicate returns a small, typed result; EvidenceBuilder writes cards
# ------------------------------------------------------------
from __future__ import annotations

from app.knowledge.criteria.protocols import Context, DbLike
from app.knowledge.criteria.utils import predicate

# Only entities common to Sparx/Cameo exports
_EXPECTED: tuple[str, ...] = (
    "t_package",
    "t_object",
    "t_objectconstraint",
    "t_objectproperties",
    "t_attribute",
    "t_attributetag",
    "t_operation",
    "t_operationparams",
    "t_connector",
    "t_connectortag",
    "t_diagram",
    "t_diagramobjects",
    "t_diagramlinks",
    "t_xref",
)


# DuckDB: look in information_schema.tables, include both BASE TABLE and VIEW
def _present_tables(db: DbLike) -> set[str]:
    ph = ",".join(["?"] * len(_EXPECTED))
    sql = f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name IN ({ph})
          AND table_type IN ('BASE TABLE','VIEW')
    """
    return {r[0] for r in db.execute(sql, _EXPECTED).fetchall()}


def _core(db: DbLike, ctx: Context):
    """Run the MML-1 check; decorator emits Evidence v2 cards (summary-only)."""

    present = _present_tables(db)

    # row counts for the expected set (views OK)
    row_counts: dict[str, int] = {}
    total_rows = 0
    nonempty: list[str] = []
    for t in _EXPECTED:
        if t in present:
            n = int(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            row_counts[t] = n
            total_rows += n
            if n > 0:
                nonempty.append(t)
        else:
            row_counts[t] = 0

    missing = [t for t in _EXPECTED if t not in present]
    passed = (len(missing) == 0) and (len(nonempty) > 0)

    # Minimal counts for the summary card (numbers only; details can go in meta later)
    counts = {
        "expected": len(_EXPECTED),
        "present": len(present),
        "nonempty": len(nonempty),
        "total_rows": total_rows,
    }

    # Universal summary for UI: ok/total
    measure = {
        "ok": counts["nonempty"],
        "total": counts["expected"],
    }

    # How many of the expected core tables are actually populated?
    if counts["expected"]:
        coverage_ratio = counts["nonempty"] / counts["expected"]
    else:
        coverage_ratio = 0.0

    # Minimal return; decorator will infer probe/mml and emit evidence
    return {
        "passed": passed,
        "counts": counts,
        "measure": measure,
        "facts": [],
        "source_tables": list(_EXPECTED),
        "domain": "Repository Sanity",
        "severity": (
            "high"
            if coverage_ratio < 0.5
            else "medium"
            if coverage_ratio < 1.0
            else "info"
        ),
    }


# Export evaluate for the loader
evaluate = predicate(_core)
