# app/api/v1/jobs.py
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

# Read-only dependency: this endpoint never mutates job state; only fetches rows.
from app.core.jobs_db import get_job

# v1 jobs namespace:
# - Mounted under /v1 in app.main.
# - Exposes a stable, poll-friendly read endpoint for async pipelines.
router = APIRouter()
logger = logging.getLogger(__name__)


# GET /jobs/{job_id}:
# - 200: normalized job status payload
# - 404: unknown job_id
# Poll-safe: no side effects; keep keys stable for frontend consumers.
@router.get("/{job_id}")
def read_job(job_id: str):
    row = get_job(job_id)
    if not row:
        logger.warning("jobs.read not_found", extra={"job_id": job_id})
        raise HTTPException(status_code=404, detail="job_not_found")

    logger.info(
        "jobs.read",
        extra={
            "job_id": row["id"],
            "model_id": row["model_id"],
            "status": row["status"],
            "progress": row["progress"],
        },
    )

    # Response contract:
    # - "message" may be empty; "timings" optional (dict when present).
    # - "links.self" and "links.result" enable simple client navigation.
    return {
        "job_id": row["id"],
        "model_id": row["model_id"],
        "status": row["status"],
        "progress": row["progress"],
        "message": row.get("message") or "",
        "timings": row.get("timings"),  # parsed dict if present
        "links": {
            "self": f"/v1/jobs/{row['id']}",
            "result": f"/v1/models/{row['model_id']}",
        },
    }
