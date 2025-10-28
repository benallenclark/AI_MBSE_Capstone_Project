# ------------------------------------------------------------
# Module: app/api/v1/health.py
# Purpose: Provide lightweight health and readiness endpoints for the MBSE Maturity backend.
# ------------------------------------------------------------

"""Health check endpoints for the MBSE Maturity backend.

Summary:
    Provides lightweight readiness probes used by CI/CD pipelines,
    container orchestrators (Kubernetes), and local developers
    to verify that the API and its dependencies are responsive.

Details:
    - The `/v1/health/ready` route checks whether critical subsystems
      (e.g., temporary database, cache, registry) are available.
    - Returns HTTP 200 with `{"status": "ready"}` when all checks pass.
    - Returns HTTP 503 with `{"status": "degraded"}` if a dependency fails.
    - Logs all events under the `maturity.api.health` logger for observability.

Developer Guidance:
    - Keep this endpoint fast and non-blocking.
    - Add dependency checks here only if they are essential to readiness.
    - Avoid long I/O operations; perform lightweight pings or status probes.
    - Always return a valid JSON payload—never raise uncaught exceptions.
    - Use structured logging instead of print statements for consistency.
"""

from fastapi import APIRouter, Response
import logging

# -----------------------------------------------------------------------------
# Router setup
# -----------------------------------------------------------------------------
router: APIRouter = APIRouter()
log = logging.getLogger("maturity.api.health")


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

    Example:
        GET /v1/health/ready → {"status": "ready"}
        (if failure) → 503 {"status": "degraded"}
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