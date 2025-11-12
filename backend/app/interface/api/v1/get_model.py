# ------------------------------------------------------------
# Module: app/interface/v1/routes/get_model.py
# Purpose: Serve the latest analysis summary for a given model.
# ------------------------------------------------------------

"""Expose an endpoint returning the latest maturity analysis summary
for a specific model. Verifies all dependencies exist and normalizes
results into the `AnalyzeContract` API shape.

Responsibilities
----------------
- Validate model directory, DuckDB file, and job existence.
- Read persisted summary data via services.models_read.
- Normalize evidence and compute total/pass/fail counts.
- Return typed `AnalyzeContract` or raise structured HTTP errors.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response

from app.infra.core import paths
from app.infra.core.config import settings
from app.interface.api.v1.models import AnalyzeContract
from app.interface.api.v1.serializers.analysis import normalize_results
from app.interface.bridge.get_model import get_latest_job, read_model_summary

router = APIRouter()
log = logging.getLogger("maturity.api.models")


# GET /v1/models/{model_id} → latest analysis summary as AnalyzeContract.
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
    # We rely on summary.api.json now; DuckDB may be pruned post-run.
    api_path = paths.model_dir(model_id) / "summary.api.json"
    if not api_path.exists():
        raise HTTPException(status_code=404, detail="summary_not_found")

    # A model is only valid if at least one job has been successfully completed.
    if not get_latest_job(model_id):
        raise HTTPException(status_code=404, detail="model_job_not_found")

    try:
        level, evidence, vendor, version = read_model_summary(model_id)
        # Normalize evidence into lightweight API results (redacted for UI).
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
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="summary_not_found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        log.exception("read_model_failed model_id=%s", model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
