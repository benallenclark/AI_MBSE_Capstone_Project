# ------------------------------------------------------------
# Module: app/interface/bridge/get_model.py
# Purpose: Read and summarize model analysis results from stored DuckDB and job data.
# ------------------------------------------------------------

"""Functions for retrieving model job metadata and computing model summaries.

This module reads analysis data from per-model DuckDB files and associated
job metadata to derive the latest maturity levels and evidence summaries.

Responsibilities
----------------
- Retrieve the most recent job entry for a given model.
- Coerce flexible maturity-level representations into standardized integers.
- Execute predicate evaluations against model databases.
- Return summarized model metadata and analysis results.

Notes
-----
- Uses a private `_jobs_connect` helper (TODO in import).
- `get_latest_job` relies on `zip(..., strict=False)` (requires Python ≥3.11).
"""

from __future__ import annotations

import json

from app.infra.core import paths
from app.infra.core.jobs_db import _connect as _jobs_connect  # TODO: public helper
from app.interface.api.v1.models import EvidenceItem


def get_latest_job(model_id: str) -> dict | None:
    con = _jobs_connect()
    try:
        cur = con.execute(
            "SELECT * FROM jobs WHERE model_id=? ORDER BY updated_at DESC LIMIT 1",
            (model_id,),
        )
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
        return dict(zip(cols, row, strict=False)) if row else None
    finally:
        con.close()


def _coerce_maturity_level(level_obj) -> int:
    if isinstance(level_obj, int):
        return level_obj
    if isinstance(level_obj, (tuple, list)) and level_obj:
        return int(level_obj[0])
    if isinstance(level_obj, str):
        return int(level_obj.split("/", 1)[0])
    raise ValueError(f"unsupported maturity level type: {type(level_obj).__name__}")


def _row_to_evidence(row: dict) -> EvidenceItem:
    """
    Accept both shapes:
      - {"predicate": "mml_1.predicate_name", "tier": 1, "passed": true}
      - {"id": "mml_1:predicate_name", "mml": 1, "passed": true}
    """
    if "predicate" in row:
        pid = str(row.get("predicate", "")).replace(".", ":")
    elif "id" in row:
        pid = str(row.get("id", ""))
    else:
        pid = ""  # schema error; still return a safe placeholder

    return EvidenceItem(
        predicate=pid,
        passed=bool(row.get("passed", False)),
        details={},  # UI summary is redacted by design
    )


def read_model_summary(model_id: str) -> tuple[int, list[EvidenceItem], str, str]:
    model_dir = paths.model_dir(model_id)
    job = get_latest_job(model_id) or {}
    vendor = str(job.get("vendor", ""))
    version = str(job.get("version", ""))

    api_path = model_dir / "summary.api.json"
    if not api_path.exists():
        raise FileNotFoundError(f"summary_api_not_found: {api_path}")

    data = json.loads(api_path.read_text(encoding="utf-8"))
    lvl = _coerce_maturity_level(data.get("maturity_level", 0))

    model_meta = data.get("model") or {}
    vendor = str(model_meta.get("vendor", vendor))
    version = str(model_meta.get("version", version))

    results = data.get("results") or []
    ev = []
    for r in results:
        # r has keys id, mml, passed, details (already redacted/safe)
        pid = str(r.get("id", ""))
        det = r.get("details") or {}
        ev.append(
            EvidenceItem(
                predicate=pid, passed=bool(r.get("passed", False)), details=det
            )
        )

    return lvl, ev, vendor, version
