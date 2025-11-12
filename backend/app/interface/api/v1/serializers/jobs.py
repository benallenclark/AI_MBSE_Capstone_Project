# ------------------------------------------------------------
# Module: app/api/v1/serializers/jobs.py
# Purpose: Shape raw job database rows into structured public API payloads.
# ------------------------------------------------------------

"""Convert database job records into public-facing API payloads.
Ensures all fields are safe, standardized, and ready for external clients
while maintaining consistency and defensive defaults.

Responsibilities
----------------
- Normalize database rows into JSON-serializable job payloads.
- Apply safe defaults for missing or malformed fields.
- Construct canonical self/result links for job navigation.
- Keep serialization deterministic and side-effect free.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


# Convert raw DB row into clean, structured API job payload.
def to_job_payload(row: Mapping[str, Any]) -> dict:
    """Transform a raw DB job row into a clean public API payload.

    Args:
        row: Mapping of job fields from the database.

    Returns:
        dict: Sanitized and structured job representation for API responses.
    """
    # Default missing or null statuses to "queued"
    status = row.get("status") or "queued"

    # Defensive parse: progress may be missing or invalid (e.g. None, str)
    try:
        progress = int(row.get("progress", 0))
    except Exception:
        progress = 0

    # Message is optional and user-facing
    message = row.get("message") or ""

    # Only include timings if they are well-formed dicts
    timings = row.get("timings") if isinstance(row.get("timings"), dict) else None

    # DB layer must always provide these keys
    job_id = row["id"]
    model_id = row["model_id"]
    return {
        "job_id": job_id,
        "model_id": model_id,
        "status": status,
        "progress": progress,
        "message": message,
        "timings": timings,
        "links": {
            "self": f"/v1/jobs/{job_id}",
            "result": f"/v1/models/{model_id}",
        },
    }
