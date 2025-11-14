# ------------------------------------------------------------
# Module: app/knowledge/diagnostics/missing_ports.py
# Purpose: Deterministic diagnostic for MML-2 'block_has_port' issues.
# ------------------------------------------------------------
from __future__ import annotations

import sqlite3

from app.artifacts.rag.db import connect


def missing_ports(scope: dict, limit: int = 200) -> list[dict]:
    """Return blocks with has_issue=1 for predicate mml_2.block_has_port."""
    con = connect(scope)
    con.row_factory = sqlite3.Row
    q = """
      SELECT d.doc_id,
             d.title,
             json_extract(d.json_metadata,'$.subject_id')   AS subject_id,
             json_extract(d.json_metadata,'$.subject_name') AS subject_name
      FROM doc d
      WHERE d.model_id=? AND d.vendor=? AND d.version=?
        AND d.probe_id='mml_2.block_has_port'
        AND d.doc_type='block'
        AND json_extract(d.json_metadata,'$.has_issue')=1
      ORDER BY subject_name
      LIMIT ?
    """
    rows = con.execute(
        q, (scope["model_id"], scope["vendor"], scope["version"], limit)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]
