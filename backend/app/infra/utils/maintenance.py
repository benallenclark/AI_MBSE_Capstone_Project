# ------------------------------------------------------------
# Module: app/infra/utils/maintenance.py
# Purpose: Centralized ops hygiene (pre: wipe runtime; post: snapshot+prune).
# ------------------------------------------------------------
from __future__ import annotations

import logging

from app.infra.core import paths

log = logging.getLogger(__name__)


def pre_run_cleanup(model_id: str) -> None:
    """
    Clean the *model's runtime* (jsonl/parquet/duckdb/rag/evidence contents),
    but DO NOT delete model.xml. This avoids deleting the upload.
    """
    report = paths.wipe_model_runtime(model_id)  # safe, XML-preserving
    log.info(
        "pre_run_cleanup model_id=%s kept=%s removed=%s",
        model_id,
        report.get("kept"),
        report.get("removed"),
    )


def post_run_cleanup(model_id: str) -> None:
    """
    End-of-run: snapshot evidence, then prune intermediates to only what's needed
    for RAG + get_model (evidence.jsonl, summary.json, rag.sqlite).
    """
    try:
        dest = paths.snapshot_evidence(model_id)
        if dest:
            log.info("snapshot_evidence ok model_id=%s dest=%s", model_id, dest)
        else:
            log.info(
                "snapshot_evidence skipped model_id=%s reason=no_evidence", model_id
            )
    except Exception:
        log.exception("snapshot_evidence failed model_id=%s", model_id)

    report = paths.prune_model_runtime(model_id)
    log.info(
        "post_run_prune model_id=%s kept=%s removed=%s",
        model_id,
        report.get("kept"),
        report.get("removed"),
    )
