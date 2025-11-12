# ------------------------------------------------------------
# Module: app/core/logging.py
# Purpose: Centralized configuration for unified logging across the MBSE API stack.
# ------------------------------------------------------------

"""Configure unified, stdout-based logging for the MBSE Maturity API.

Responsibilities
----------------
- Initialize a single consistent logging setup at app startup.
- Respect env-based toggles from `settings` (log level, mute, access logs).
- Align Uvicorn’s loggers with the app-level configuration.
- Provide Docker/K8s-friendly structured output to stdout.

Notes
-----
- `basicConfig` is idempotent unless `force=True` (Python ≥3.8).
- Use `settings.MUTE_ALL_LOGS` to silence all logs for CI or benchmarks.
"""

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    """Initialize global logging once at startup.

    Notes
    -----
    - Hard-mutes all logs if `MUTE_ALL_LOGS` is set.
    - Ensures stdout formatting for container log aggregation.
    - Keeps Uvicorn loggers aligned with app-level log level.
    """
    # Hard mute for CI/benchmarks: disables ALL logging below CRITICAL globally.
    if settings.MUTE_ALL_LOGS:
        logging.disable(logging.CRITICAL)
        return

    # Configure single stdout handler with uniform, timestamped format.
    logging.basicConfig(
        level=settings.LOG_LEVEL,  # e.g. "INFO", "DEBUG", "ERROR"
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    # Keep Uvicorn loggers consistent with app-level log level.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(settings.LOG_LEVEL)

    # Optionally suppress noisy per-request access logs.
    if not settings.ACCESS_LOG:
        logging.getLogger("uvicorn.access").disabled = True
