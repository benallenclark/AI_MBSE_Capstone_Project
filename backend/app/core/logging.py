# ------------------------------------------------------------
# Module: app/core/logging.py
# Purpose: Configure unified logging for the MBSE Maturity API and its dependencies.
# ------------------------------------------------------------

"""Unified logging configuration for the MBSE Maturity API.

Summary:
    Centralizes all logging setup logic for consistent, environment-driven
    behavior across FastAPI, Uvicorn, and internal modules.

Details:
    - Reads verbosity and access log settings from `app.core.config.settings`.
    - Ensures all loggers (including Uvicorn’s internal ones) share the same level.
    - Supports a full mute mode for minimal CI/CD or benchmark runs.
    - Uses a simple stdout stream handler suitable for Docker and Kubernetes logs.

Developer Guidance:
    - Call `configure_logging()` once during application startup (see `app/main.py`).
    - Always retrieve module loggers via `logging.getLogger(__name__)`.
    - Never modify logging configuration directly in other modules.
    - For CI/CD or performance tests, set `MUTE_ALL_LOGS=True` in `.env`.
    - Keep logging consistent—avoid print statements and ad-hoc formats.
"""

import logging
import sys
from app.core.config import settings


def configure_logging() -> None:
    """Configure global logging behavior for the entire app.

    Behavior:
        - Disables all logs if `MUTE_ALL_LOGS` is True.
        - Otherwise, applies standard log formatting and levels.
        - Aligns Uvicorn's internal loggers with the global settings.
        - Disables Uvicorn access logs if `ACCESS_LOG` is False.

    Example:
        >>> from app.core.logging import configure_logging
        >>> configure_logging()
        >>> log = logging.getLogger("maturity")
        >>> log.info("Logging configured")
    """
    if settings.MUTE_ALL_LOGS:
        # Completely silence all logs (useful for tests or benchmarks)
        logging.disable(logging.CRITICAL)
        return

    # Configure global logging format and level
    logging.basicConfig(
        level=settings.LOG_LEVEL,  # e.g. "INFO", "DEBUG", "ERROR"
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    # Sync all key loggers (including uvicorn internals)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(settings.LOG_LEVEL)

    # Optionally disable access logs entirely
    if not settings.ACCESS_LOG:
        logging.getLogger("uvicorn.access").disabled = True
