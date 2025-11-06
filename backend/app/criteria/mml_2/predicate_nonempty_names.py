# app/criteria/mml_1/predicate_nonempty_names.py
from __future__ import annotations
import time
from pathlib import Path
from typing import List, Dict
from app.criteria.protocols import Context, DbLike
from app.evidence.types import PredicateOutput
from app.evidence.writer import emit_evidence
from app.criteria.utils import predicate


_SQL_ELEMENT = """
  SELECT id, kind
  FROM element
  WHERE COALESCE(TRIM(name), '') = ''
"""

_SQL_T_OBJECT = """
  SELECT CAST(Object_ID AS BIGINT) AS id, Object_Type AS kind
  FROM t_object
  WHERE COALESCE(TRIM(Name), '') = ''
"""

def _has_table(db: DbLike, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='main' AND table_name=?",
        [name],
    ).fetchone()
    return bool(row)

def _core(db: DbLike, ctx: Context) -> Dict:
    use_element = _has_table(db, "element")
    src_table   = "element" if use_element else "t_object"
    sql_off     = _SQL_ELEMENT if use_element else _SQL_T_OBJECT
    sql_total   = "SELECT COUNT(*) FROM element" if use_element else "SELECT COUNT(*) FROM t_object"

    offenders = db.execute(sql_off).fetchall()
    total     = int(db.execute(sql_total).fetchone()[0])

    fail   = len(offenders)
    passed = (fail == 0)

    facts: List[Dict] = [
        {"subject_id": r[0], "subject_type": r[1], "has_issue": True, "meta": {"issue": "empty_name"}}
        for r in offenders
    ]
    counts = {"total_elements": total, "unnamed": fail, "named": total - fail}
    # Universal summary for UI: ok/total/ratio
    measure = {
        "ok": counts["named"],
        "total": counts["total_elements"],
        "ratio": (counts["named"] / counts["total_elements"]) if counts["total_elements"] else 0.0,
    }

    
    
    # Minimal payload; decorator infers mml/probe_id and emits evidence for you
    return {
        "passed": passed,
        "counts": counts,
        "measure": measure,
        "facts": facts,
        "source_tables": [src_table],
    }

# Export an `evaluate` symbol the loader expects
evaluate = predicate(_core)