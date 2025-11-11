# ------------------------------------------------------------
# Module: app/core/logging.py
# Purpose: Configure unified logging for the MBSE Maturity API and its dependencies.
# ------------------------------------------------------------

import logging
import sys

# Importing settings parses env/.env once; 
# keep imports here to avoid circulars.
from app.core.config import settings

# Global logging setup:
# - Call exactly once at startup; basicConfig is a no-op if handlers already exist.
# - If tests need to reconfigure mid-run, prefer force=True or clear handlers explicitly.
def configure_logging() -> None:

    # Hard mute for CI/benchmarks: disables ALL logging below CRITICAL globally.
    if settings.MUTE_ALL_LOGS:
        logging.disable(logging.CRITICAL)
        return

    # Single stdout handler with uniform format; suitable for Docker/K8s aggregation.
    # Note: basicConfig won't replace existing handlers unless force=True (Python 3.8+).
    logging.basicConfig(
        level=settings.LOG_LEVEL,  # e.g. "INFO", "DEBUG", "ERROR"
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    # Keep Uvicorn loggers at the same level as the app; 
    # handlers come from basicConfig.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(settings.LOG_LEVEL)

    # Disable request-per-line access logs (useful to reduce noise in prod or tests).
    if not settings.ACCESS_LOG:
        logging.getLogger("uvicorn.access").disabled = True
