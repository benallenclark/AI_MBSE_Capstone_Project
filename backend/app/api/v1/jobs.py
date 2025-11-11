# app/api/v1/jobs.py
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

# Read-only dependency: this endpoint never mutates job state; only fetches rows.
from app.core.jobs_db import JobRow, get_job

# v1 jobs namespace:
# - Mounted under /v1 in app.main.
# - Exposes a stable, poll-friendly read endpoint for async pipelines.
router = APIRouter()
logger = logging.getLogger(__name__)


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

    return _payload(row)
