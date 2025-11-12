# ------------------------------------------------------------
# Module: app/api/v1/jobs.py
# Purpose: Expose read-only job status endpoint for async pipelines.
# ------------------------------------------------------------

"""Provide a stable, poll-friendly endpoint for job status queries.
Jobs are immutable from this route—only retrieved and normalized for
frontend consumption with consistent payload structure.

Responsibilities
----------------
- Fetch job records by ID via core.jobs_db.
- Normalize fields into a predictable, JSON-safe payload.
- Return 404 for missing jobs and 200 for valid ones.
- Maintain consistent field names for frontend polling.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.jobs_db import JobRow, get_job

# Router configuration for /v1/jobs namespace.
router = APIRouter()
logger = logging.getLogger(__name__)


# Build normalized API payload from a raw JobRow record.
def _payload(row: JobRow) -> dict:
    """Build the exact wire shape the frontend expects."""
    status = row.get("status") or "queued"
    # progress is guaranteed int in JobRow; still coerce defensively
    try:
        progress = int(row.get("progress", 0))
    except Exception:
        progress = 0
    message = row.get("message") or ""
    timings = row.get("timings") if isinstance(row.get("timings"), dict) else None
    return {
        "job_id": row["id"],
        "model_id": row["model_id"],
        "status": status,
        "progress": progress,
        "message": message,
        "timings": timings,
        "links": {
            "self": f"/v1/jobs/{row['id']}",
            "result": f"/v1/models/{row['model_id']}",
        },
    }


# Handle GET /v1/jobs/{job_id} to retrieve a job’s current status.
@router.get("/{job_id}")
def read_job(job_id: str):
    """Retrieve and normalize job record by ID for frontend polling."""
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

    return _payload(row)
