# ------------------------------------------------------------
# Module: app/api/v1/routes.py
# Purpose: Define and compose all version 1 API routers.
# ------------------------------------------------------------

"""API router entrypoint for version 1 of the MBSE Maturity backend.

Summary:
    Defines the version-scoped FastAPI router (`/v1`) and mounts sub-routers
    for health checks and model analysis endpoints.

Details:
    Keeping each API version in its own router supports backward compatibility.
    When `/v2` or later versions are added, this structure can be duplicated
    without affecting existing routes.

Developer Guidance:
    - To add a new functional area (e.g., `/v1/users`), create
      `app/api/v1/users.py` with its own `router` and include it here.
    - Keep versioned routes isolated to simplify long-term API versioning.
    - Avoid embedding business logic; this module should only compose routers.
"""

from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.analyze import router as analyze_router

# -----------------------------------------------------------------------------
# Create the root router for version 1
# -----------------------------------------------------------------------------
router: APIRouter = APIRouter()

# -----------------------------------------------------------------------------
# Mount sub-routers
# -----------------------------------------------------------------------------
router.include_router(
    health_router,
    prefix="/health",
    tags=["health"],
)

router.include_router(
    analyze_router,
    prefix="/analyze",
    tags=["analyze"],
)
