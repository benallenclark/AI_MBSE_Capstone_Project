# ------------------------------------------------------------
# Module: app/core/lifespan.py
# Purpose: Manage FastAPI startup and shutdown lifecycle events.
# ------------------------------------------------------------

"""FastAPI lifespan context for startup and shutdown events.

Summary:
    Provides a centralized async context manager to handle application
    startup and teardown phases. Ensures consistent initialization and
    cleanup of shared resources, with timing and structured logging for
    observability.

Details:
    - Automatically invoked by FastAPI at app startup and shutdown.
    - Use the startup phase for initializing global resources (e.g., DB pools,
      registries, caches).
    - Use the shutdown phase for releasing resources to prevent leaks.
    - Logs durations and errors to assist with operational monitoring.

Developer Guidance:
    - Store shared objects on `app.state.<name>` for global access.
    - Prefer async-compatible initialization; avoid blocking calls.
    - Log all major lifecycle steps for debugging and visibility.
    - Do not silently ignore startup/shutdown errors—fail fast and log them.
    - Extend this file only with cross-cutting lifecycle concerns,
      not business logic.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
import time

logger = logging.getLogger("maturity.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown phases for the FastAPI application.

    Args:
        app (FastAPI): The FastAPI app instance being initialized.

    Yields:
        None: Control is yielded back to the FastAPI runtime after startup.

    Behavior:
        - Logs startup and shutdown phases with elapsed time.
        - Use this hook to initialize or release global resources.

    Example:
        >>> @asynccontextmanager
        ... async def lifespan(app):
        ...     app.state.db = await make_db_pool()
        ...     yield
        ...     await app.state.db.close()
    """
    t0 = time.perf_counter()
    try:
        # -----------------------------
        # Startup section
        # -----------------------------
        # Initialize shared state objects here (e.g., database pool, registry)
        logger.info("startup begin")
        # app.state.db = await make_db_pool()
        # app.state.registry = await load_registry()
        logger.info("startup ok duration_ms=%.1f", (time.perf_counter() - t0) * 1000)
        yield
    except Exception:
        logger.exception("startup failed")
        raise
    finally:
        # -----------------------------
        # Shutdown section
        # -----------------------------
        try:
            logger.info("shutdown begin")
            # clean up shared resources here
            # await app.state.db.close()
            logger.info("shutdown ok")
        except Exception:
            logger.exception("shutdown failed")
