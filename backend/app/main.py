# ------------------------------------------------------------
# Module: app/main.py
# Purpose: FastAPI entrypoint for the MBSE Maturity backend.
# ------------------------------------------------------------


from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse

from app.api.routes import router
from app.core.config import settings
from app.core.lifespan import lifespan as _orig_lifespan
from app.core.logging_config import configure_logging
from app.core import paths

__docformat__ = "google"
log = logging.getLogger("startup")

# Lifespan wrapper:
# - Keep this fast and deterministic (e.g., path logging).
# - Heavy I/O or model warmups belong in background tasks, not here.
@asynccontextmanager
async def _lifespan(app: FastAPI):
    for k, v in paths.log_path_map().items():
    # If these paths look wrong, fix env in app/core/config.py—do not override here.
        log.info("path %s = %s", k, v)
    async with _orig_lifespan(app):
        yield

def create_app() -> FastAPI:
    # Configure logging FIRST so all startup logs 
    # (including uvicorn) share the same level/format.
    configure_logging()
    
    # API surface:
    # - docs_url is versioned (/v1/docs) for forward compatibility.
    # - redoc disabled to reduce attack surface and maintenance.
    # - lifespan uses our wrapper for deterministic boot logs.
    app = FastAPI(
        title=f"MBSE Maturity API ({settings.APP_ENV})",
        version="0.1.0",
        docs_url="/v1/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )
    
    # CORS:
    # - With allow_credentials=True, browsers require explicit origins (no "*").
    # - settings.CORS_ORIGINS should be strict in prod (scheme+host+port).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Public endpoints are mounted under /v1.
    # Add /v2 side-by-side later; keep /v1 for backward compatibility.
    app.include_router(router, prefix="/v1")

    
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        # Keep server logs consistent with app LOG_LEVEL;
        # handler setup lives in configure_logging().
        logging.getLogger(name).setLevel(settings.LOG_LEVEL)
    return app

# Import target for process managers: "app.main:app".
# Do not instantiate FastAPI elsewhere—always import this app.
app = create_app()

# Return 204 to silence automatic browser favicon requests during health checks/dev.
@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    """Landing page with link to docs."""
    return HTMLResponse(
        "<html><body>"
        "<h1>MBSE Maturity API</h1>"
        '<p><a href="/v1/docs">Open API Docs</a></p>'
        "</body></html>"
    )

@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)

# Development only. In production run: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
# reload=True uses a file watcher; avoid outside local iteration.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
