# ------------------------------------------------------------
# Module: app/core/lifespan.py
# Purpose: Manage FastAPI startup and shutdown lifecycle events.
# ------------------------------------------------------------

"""FastAPI lifespan context for startup and shutdown events.

Responsibilities
----------------
- Provide a centralized async context manager for startup/shutdown phases.
- Initialize shared resources (e.g., databases, registries, caches) at startup.
- Release or clean up those resources at shutdown.
- Log timings and errors for observability and operational monitoring.

Developer Guidance
------------------
- Attach shared objects to `app.state.<name>` for global access.
- Prefer async-compatible initialization; avoid blocking I/O in async context.
- Fail fast on startup errors—don’t silently ignore them.
- Extend only for cross-cutting lifecycle concerns (not business logic).
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import jobs_db

logger = logging.getLogger("maturity.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI application startup and shutdown phases.

    Args:
        app: FastAPI application instance.

    Yields:
        None. Control returns to FastAPI after successful startup.

    Behavior:
        - Logs startup and shutdown with elapsed time.
        - Initializes shared components (e.g., jobs DB, registries).
        - Ensures schema creation for job tracking.
        - Cleans up resources gracefully on shutdown.

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
        # Ensure jobs DB schema exists (idempotent, quick)
        jobs_db.ensure_initialized()
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
            # clean up shared resources if initialized
            # await app.state.db.close()
            logger.info("shutdown ok")
        except Exception:
            logger.exception("shutdown failed")
