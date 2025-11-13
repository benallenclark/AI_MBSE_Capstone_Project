# ------------------------------------------------------------
# Module: app/interface/api/v1/get_model.py
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

from fastapi import APIRouter, HTTPException

from app.interface.api.v1.models import AnalyzeContract
from app.interface.bridge.get_model import get_latest_job, read_model_summary

router = APIRouter()
log = logging.getLogger("maturity.api.models")


# GET /v1/models/{model_id} → latest analysis summary as AnalyzeContract.
@router.get(
    "/{model_id}", response_model=AnalyzeContract, response_model_exclude_none=True
)
@router.get("/{model_id}", response_model=AnalyzeContract)
def read_model(model_id: str):
    if not get_latest_job(model_id):
        raise HTTPException(status_code=404, detail="model_job_not_found")

    try:
        summary = read_model_summary(model_id)
        return AnalyzeContract(**summary)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="summary_not_found")
