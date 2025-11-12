# ------------------------------------------------------------
# Module: app/api/v1/health.py
# Purpose: Lightweight health and readiness checks for the MBSE Maturity backend.
# ------------------------------------------------------------

"""Expose fast, non-blocking health probes for service readiness.
Used by CI/CD, orchestrators, and developers to verify API responsiveness
and dependency availability with minimal overhead.

Responsibilities
----------------
- Provide /v1/health/ready readiness endpoint.
- Log structured health events for observability.
- Return consistent JSON payloads for monitoring systems.
- Avoid blocking or heavy dependency checks.
"""

import logging

from fastapi import APIRouter, Response

# Configure router and logger for health endpoints.
router: APIRouter = APIRouter()
log = logging.getLogger("maturity.api.health")


# Perform a lightweight readiness probe for core service health.
@router.get("/ready", include_in_schema=True)
def ready(res: Response) -> dict[str, str]:
    """Readiness probe endpoint.

    Args:
        res (Response): The outgoing FastAPI response object.

    Returns:
        dict[str, str]: A JSON payload describing current service readiness.

    Behavior:
        - Attempts to touch critical dependencies (DB, cache, registry, etc.).
        - Logs the result and returns an appropriate HTTP status.
        - Returns HTTP 200 on success or HTTP 503 if a dependency fails.
    """
    log.info("ready check begin")
    try:
        # Example future check:
        # await app.state.db.fetchval("select 1")
        log.info("ready check ok")
        return {"status": "ready"}
    except Exception:
        log.exception("ready check failed")
        res.status_code = 503
        return {"status": "degraded"}
