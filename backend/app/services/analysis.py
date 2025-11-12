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

log = logging.getLogger("maturity.service.analysis")


# Open the per-model DuckDB database with caching enabled.
def _open_model_db(model_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(model_dir / "model.duckdb"))
    con.execute("PRAGMA enable_object_cache=true;")
    return con


# Run synchronous predicate evaluation after ingest (no RAG).
def run_sync_predicates(
    *, model_id: str, vendor: str, version: str, xml_path: Path
) -> tuple[int, list]:
    """
    Ingest without RAG, then run predicates synchronously against the model DB.
    Returns (maturity_level, evidence_list).
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


# Perform post-ingest tasks like Parquet mirroring and RAG bootstrapping (non-critical).
def post_ingest_best_effort(*, model_id: str) -> None:
    """
    Best-effort post-ingest actions: mirror JSONL→Parquet and bootstrap RAG.
    Never raises.
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


# Run the complete analysis pipeline as a background job with job status tracking.
def run_pipeline_job(job_id: str, model_id: str) -> None:
    """
    Background pipeline: ingest → predicates → RAG → update job status.
    Never raises across the boundary; reports failure in job row.
    """
    try:
        update_status(job_id, "running", progress=10)
        xml_path = paths.model_dir(model_id) / "model.xml"
        if not xml_path.exists():
            update_status(
                job_id, "failed", progress=100, message=f"missing xml: {xml_path}"
            )
            return
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
        update_status(
            job_id, "failed", progress=100, message=f"{type(e).__name__}: {e}"
        )
