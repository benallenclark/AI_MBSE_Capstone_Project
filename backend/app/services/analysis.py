# ------------------------------------------------------------
# Module: app/services/analysis.py
# Purpose: Coordinate analysis workflows including ingest, predicate runs, and pipeline orchestration.
# ------------------------------------------------------------

"""High-level orchestration for model analysis workflows.

This module manages the full analysis lifecycle — from ingest to predicate evaluation
and RAG bootstrapping — ensuring robustness and consistent job status updates.

Responsibilities
----------------
- Open and manage per-model DuckDB connections.
- Run synchronous predicate evaluations for model maturity scoring.
- Execute post-ingest side effects safely (e.g., Parquet mirroring, RAG bootstrap).
- Orchestrate background pipeline jobs and maintain job status.

Notes
-----
- All background jobs must handle their own error reporting via `update_status`.
- All post-ingest routines are best-effort (never raise).
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from app.core import paths
from app.core.jobs_db import get_job, update_status
from app.core.orchestrator import run as orchestrate_run
from app.criteria.protocols import Context
from app.criteria.runner import run_predicates
from app.evidence.writer import mirror_jsonl_to_parquet

# Dedicated logger for analysis service operations
log = logging.getLogger("maturity.service.analysis")


def _open_model_db(model_dir: Path) -> duckdb.DuckDBPyConnection:
    """Open the DuckDB database for the given model directory with caching enabled."""
    con = duckdb.connect(str(model_dir / "model.duckdb"))
    con.execute("PRAGMA enable_object_cache=true;")
    return con


def run_sync_predicates(
    *, model_id: str, vendor: str, version: str, xml_path: Path
) -> tuple[int, list]:
    """
    Run synchronous predicate evaluation for a model (no RAG step).

    Returns
    -------
    tuple[int, list]
        The maturity level and evidence list.

    Notes
    -----
    - Runs `orchestrate_run` with `build_rag=False` and `run_predicates=False`
      to perform a clean ingest before evaluation.
    - Opens the model’s DuckDB database for local predicate runs.
    - Safe for repeated calls (idempotent ingest overwrite).
    """
    model_dir = paths.model_dir(model_id)
    orchestrate_run(
        model_id=model_id,
        xml_path=xml_path,
        overwrite=True,
        build_rag=False,
        run_predicates=False,
    )
    with _open_model_db(model_dir) as con:
        ctx = Context(
            vendor=vendor,
            version=version,
            model_dir=model_dir,
            model_id=model_id,
            output_root=paths.MODELS_DIR,
        )
        level, evidence, _levels = run_predicates(con, ctx)
    return level, evidence


def post_ingest_best_effort(*, model_id: str) -> None:
    """
    Perform non-critical post-ingest actions: JSONL→Parquet mirroring and RAG bootstrap.

    Notes
    -----
    - Never raises exceptions; all errors are logged and suppressed.
    - Intended to run asynchronously or after main ingest completes.
    - Each step logs its own diagnostic line if skipped or failed.
    """
    model_dir = paths.model_dir(model_id)
    try:
        mirror_jsonl_to_parquet(model_dir)
    except Exception:
        log.debug(
            "post_ingest.parquet_mirror_skipped model_id=%s", model_id, exc_info=True
        )

    try:
        orchestrate_run(
            model_id=model_id, xml_path=None, overwrite=False, build_rag=True
        )
    except Exception:
        log.warning(
            "post_ingest.rag_bootstrap_failed model_id=%s", model_id, exc_info=True
        )


def run_pipeline_job(job_id: str, model_id: str) -> None:
    """
    Execute the full analysis pipeline (ingest → predicates → RAG) as a background job.

    Notes
    -----
    - Updates the job row status in `jobs_db` as it progresses.
    - Reports all failures via `update_status` instead of raising.
    - Safe for background thread or task execution.
    """
    try:
        update_status(job_id, "running", progress=10)
        xml_path = paths.model_dir(model_id) / "model.xml"
        if not xml_path.exists():
            update_status(
                job_id, "failed", progress=100, message=f"missing xml: {xml_path}"
            )
            return

        # Fetch job metadata for downstream steps (vendor/version)
        row = get_job(job_id) or {}
        vendor = row.get("vendor") or ""
        version = row.get("version") or ""

        orchestrate_run(
            model_id=model_id,
            xml_path=xml_path,
            overwrite=False,
            build_rag=True,
            run_predicates=True,
            vendor=vendor,
            version=version,
        )
        update_status(job_id, "succeeded", progress=100)

    except Exception as e:
        # Capture any pipeline failure and update job record accordingly.
        update_status(
            job_id, "failed", progress=100, message=f"{type(e).__name__}: {e}"
        )
