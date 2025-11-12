# ------------------------------------------------------------
# Module: app/api/v1/routes/models_read.py
# Purpose: FastAPI endpoint to serve the latest analysis summary for a given model.
# ------------------------------------------------------------

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from app.api.v1.models import AnalyzeContract
from app.api.v1.serializers.analysis import normalize_results
from app.core import paths
from app.core.config import settings
from app.services.models_read import get_latest_job, read_model_summary

router = APIRouter()
log = logging.getLogger("maturity.api.models")

"""
Responsibilities
----------------
- Validate that the model directory, DuckDB database, and at least one job exist.
- Read the persisted summary, normalize evidence results (with redaction), and compute pass/fail counts.
- Return an `AnalyzeContract` payload for API clients.

Error Model (HTTP)
------------------
- 404 → Missing model assets (`model_not_found`, `model_db_not_found`, `model_job_not_found`)
- 400 → Domain-layer `ValueError` (invalid/malformed data)
- 500 → Unhandled errors (logged, generic "analysis_failed" returned)
"""


@router.get(
    "/{model_id}", response_model=AnalyzeContract, response_model_exclude_none=True
)
def read_model(model_id: str, response: Response) -> AnalyzeContract:
    """Return the current analysis summary for a model.

    Args:
        model_id: Opaque model identifier (path parameter).
        response: FastAPI response object (reserved for future cache/ETag headers).

    Returns:
        AnalyzeContract: Contract containing maturity level, metadata, summary counts, and normalized results.

    Raises:
        HTTPException:
            - 404: if required model assets are missing.
            - 400: if domain validation fails.
            - 500: for unexpected exceptions (logged internally).
    """
    model_dir = paths.model_dir(model_id)
    if not model_dir.exists():
        raise HTTPException(status_code=404, detail="model_not_found")
    db_path = paths.duckdb_path(model_id)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="model_db_not_found")

    # A model is only valid if at least one job has been successfully completed.
    if not get_latest_job(model_id):
        raise HTTPException(status_code=404, detail="model_job_not_found")

    try:
        level, evidence, vendor, version = read_model_summary(model_id)
        # GOTCHA: `normalize_results` must return objects with a boolean-like `.passed` attribute.
        # Redaction is enforced here for clear summaries for the UI
        results = normalize_results(evidence, redact=True)
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        return AnalyzeContract(
            schema_version=getattr(settings, "CONTRACT_SCHEMA_VERSION", "1.0"),
            model={"vendor": vendor, "version": version},
            maturity_level=level,
            summary={"total": total, "passed": passed, "failed": failed},
            results=results,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        log.exception("read_model_failed model_id=%s", model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
