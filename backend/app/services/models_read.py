# ------------------------------------------------------------
# Module: app/services/models_read.py
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

from pathlib import Path

import duckdb

from app.core import paths
from app.core.jobs_db import (
    _connect as _jobs_connect,  # TODO: replace with public helper
)
from app.criteria.protocols import Context
from app.criteria.runner import run_predicates


def get_latest_job(model_id: str) -> dict | None:
    """Return the most recently updated job row for `model_id`, or None if missing.

    Notes
    -----
    - Orders by `updated_at` descending and limits to 1.
    - Closes the DB connection in all cases.
    """
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
    """Normalize a maturity-level value to an `int`.

    Accepts these shapes:
    - `int` → returned as-is
    - `(1, 3)` or `[1, 3]` → returns `1`
    - `"1/3"` → returns `1`

    Raises
    ------
    ValueError
        If the value type is unsupported.
    """
    if isinstance(level_obj, int):
        return level_obj
    if isinstance(level_obj, (tuple, list)) and level_obj:
        return int(level_obj[0])
    if isinstance(level_obj, str):
        return int(level_obj.split("/", 1)[0])
    raise ValueError(f"unsupported maturity level type: {type(level_obj).__name__}")


# Open the model DuckDB, run predicates, and return a summarized result.
def read_model_summary(model_id: str) -> tuple[int, list, str, str]:
    """
    Open the per-model DuckDB, run predicates, and return a compact summary.

    Returns
    -------
    tuple[int, list, str, str]
        `(maturity_level, evidence, vendor, version)`

    Notes
    -----
    - Enables DuckDB object cache for repeated predicate runs.
    - Pulls vendor/version from the latest job row when available.
    """
    model_dir: Path = paths.model_dir(model_id)
    db_path: Path = paths.duckdb_path(model_id)
    job = get_latest_job(model_id) or {}
    vendor = str(job.get("vendor", ""))
    version = str(job.get("version", ""))

    with duckdb.connect(str(db_path)) as con:
        con.execute("PRAGMA enable_object_cache=true;")
        ctx = Context(
            vendor=vendor,
            version=version,
            model_dir=model_dir,
            model_id=model_id,
            output_root=paths.MODELS_DIR,
        )
        level_obj, evidence, _levels = run_predicates(con, ctx)

    return _coerce_maturity_level(level_obj), evidence, vendor, version
