# ------------------------------------------------------------
# Module: app/main.py
# Purpose: FastAPI entrypoint for the MBSE Maturity backend.
# ------------------------------------------------------------

"""FastAPI entrypoint for the MBSE Maturity backend.

Summary:
    Provides a single construction path so CLI, tests, and production share
    the same middleware, routers, and settings.

Details:
    New contributors should start here to understand app boot and request flow.

Developer Guidance:
    - Treat this file as the canonical FastAPI app factory.
    - Do not create ad-hoc FastAPI instances elsewhere; always call `create_app()`.
    - Environment configuration comes from `app/core/config.py` and is injected
      automatically via `settings`.
    - Keep middleware, router, and logging setup centralized here to ensure
      consistent behavior across local, test, and deployment environments.
    - For local debugging, run this file directly (`python app/main.py`);
      for production, invoke with `uvicorn app.main:app`.
"""


from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from app.api.routes import router
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging

__docformat__ = "google"  # Tell Sphinx/Napoleon to parse Google-style docstrings


def create_app() -> FastAPI:
    """Build and configure the FastAPI app.

    Returns:
        FastAPI: Configured ASGI application.

    Notes:
        Single construction path so tests and CLI use identical setup.
        Ensures logging, middleware, and routers are initialized consistently.
    """
    configure_logging()  # Ensure logging format/levels are set before app init

    app = FastAPI(
        title=f"MBSE Maturity API ({settings.APP_ENV})",
        version="0.1.0",
        docs_url="/v1/docs",   # Swagger UI on a versioned path
        redoc_url=None,        # One doc UI only
        lifespan=lifespan,     # Startup/shutdown hooks (registries, timing)
    )

    # CORS: environment-driven (do not hard-code origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],   # Restrict if exposing publicly
        allow_headers=["*"],
    )

    # Compose all versioned endpoints under /v1 for stable URLs
    app.include_router(router, prefix="/v1")

    # Align uvicorn loggers with app-level LOG_LEVEL
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(settings.LOG_LEVEL)

    return app


# ASGI app instance (imported by uvicorn)
app = create_app()


@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    """Return a minimal landing page with a link to interactive docs.

    Returns:
        HTMLResponse: Simple HTML page for smoke testing.
    """
    return HTMLResponse(
        "<html><body>"
        "<h1>MBSE Maturity API</h1>"
        '<p><a href="/v1/docs">Open API Docs</a></p>'
        "</body></html>"
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return 204 to silence browser favicon requests.

    Returns:
        Response: Empty 204 response.
    """
    return Response(status_code=204)


if __name__ == "__main__":
    # Local dev server; production uses a process manager
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
