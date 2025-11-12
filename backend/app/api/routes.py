# ------------------------------------------------------------
# Module: app/api/routes.py
# Purpose: Compose and expose all v1 FastAPI routers.
# ------------------------------------------------------------

"""Central composition root for versioned API routing.
Mounts domain-specific sub-routers under /v1 with stable tag order so
OpenAPI groups remain predictable across builds.

Responsibilities
----------------
- Create the v1 APIRouter composition root.
- Mount health, analyze, jobs, and models sub-routers with prefixes.
- Group RAG sync/stream under a shared /rag prefix and tag.
- Preserve deterministic inclusion order for OpenAPI tag grouping.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.analyze import router as analyze_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.models_read import router as models_public_router
from app.api.v1.rag import router as rag_router
from app.api.v1.rag_stream import router as rag_stream_router

# v1 composition root:
# - app.main mounts this under /v1
# - Keep inclusion order stable for deterministic OpenAPI tag/group order.
router: APIRouter = APIRouter()

# Sub-routers by domain; tags double as doc group names—avoid renaming casually.
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(analyze_router, prefix="/analyze", tags=["analyze"])
router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
router.include_router(models_public_router, prefix="/models", tags=["models"])

# RAG (sync + streaming) share the /rag prefix and "rag" tag so they show together in docs.
# Ensure unique subpaths to avoid conflicts (e.g., /ask vs /ask/stream).
router.include_router(rag_router, prefix="/rag", tags=["rag"])
router.include_router(rag_stream_router, prefix="/rag", tags=["rag"])
