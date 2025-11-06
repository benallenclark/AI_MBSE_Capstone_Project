# ------------------------------------------------------------
# Module: app/api/v1/routes.py
# Purpose: Define and compose all version 1 API routers.
# ------------------------------------------------------------
from __future__ import annotations
from fastapi import APIRouter
from app.core.config import settings

# Versioned sub-routers (all under /v1)
from app.api.v1.health import router as health_router
from app.api.v1.analyze import router as analyze_router
from app.api.v1.rag import router as rag_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.rag_stream import router as rag_stream_router
from app.api.v1.schemas import public_router as models_public_router, internal_router as models_internal_router

# v1 composition root:
# - app.main mounts this under /v1
# - Keep inclusion order stable for deterministic OpenAPI tag/group order.
router: APIRouter = APIRouter()

# Sub-routers by domain; tags double as doc group names—avoid renaming casually.
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(analyze_router, prefix="/analyze", tags=["analyze"])

# RAG (sync + streaming) share the /rag prefix and "rag" tag so they show together in docs.
# Ensure unique subpaths to avoid conflicts (e.g., /ask vs /ask/stream).
router.include_router(rag_router, prefix="/rag", tags=["rag"])
router.include_router(rag_stream_router, prefix="/rag", tags=["rag"])

router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
router.include_router(models_public_router, prefix="/models", tags=["models"])

# Internal-only routes:
# - Gated by settings.EXPOSE_INTERNALS; keep False in production.
# - Consider setting include_in_schema=False inside those endpoints if you must mount them.
if getattr(settings, "EXPOSE_INTERNALS", False):
    router.include_router(models_internal_router, prefix="/models", tags=["internal"])
