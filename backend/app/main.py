# ------------------------------------------------------------
# Module: app/main.py
# Purpose: FastAPI entrypoint for the MBSE Maturity backend.
# ------------------------------------------------------------

"""FastAPI application setup and process entrypoint.

Initializes logging, configures middleware and routes, and wraps the app
lifespan to emit deterministic boot logs (paths, environment-derived dirs).

Responsibilities
----------------
- Configure logging before any startup output (including uvicorn).
- Expose a versioned API surface under `/v1`.
- Apply strict CORS settings from configuration.
- Wrap the lifespan to log resolved paths on boot.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from app.api.routes import router
from app.core import paths
from app.core.config import settings
from app.core.lifespan import lifespan as _orig_lifespan
from app.core.logging_config import configure_logging

__docformat__ = "google"
log = logging.getLogger("startup")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Wrap the base lifespan to log resolved path mappings early (fast, deterministic).

    Notes
    -----
    Heavy I/O or model warmups should run in background tasks, not here.
    """
    for k, v in paths.log_path_map().items():
        # If these paths look wrong, fix env in app/core/config.py—do not override here.
        log.info("path %s = %s", k, v)
    async with _orig_lifespan(app):
        yield


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application.

    - Configures logging first for consistent startup output.
    - Sets versioned docs at `/v1/docs` and disables ReDoc.
    - Applies CORS using configured origins (no wildcard with credentials).
    - Includes API routes under `/v1`.
    """

    configure_logging()

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
    """Return an empty response for favicon lookups (reduces noise in logs)."""
    return Response(status_code=204)


# Development only. In production run: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
# reload=True uses a file watcher; avoid outside local iteration.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
