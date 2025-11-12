# ------------------------------------------------------------
# Module: app/utils/timing.py
# Purpose: Provide timing utilities and context-based logging for performance tracking.
# ------------------------------------------------------------

"""Lightweight utilities for timing measurements and structured log timing.

This module standardizes timing measurements and logging of operation durations,
ensuring consistent observability across modules and workflows.

Responsibilities
----------------
- Measure high-resolution elapsed time in nanoseconds or milliseconds.
- Provide a consistent context manager for timing and logging operations.
- Log start, success, and failure messages with elapsed durations.
- Support optional contextual data in structured log output.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager


# Return the current high-resolution time in nanoseconds.
def now_ns() -> int:
    """Get the current high-resolution time in nanoseconds."""
    return time.perf_counter_ns()


# Compute milliseconds elapsed since a given start time in nanoseconds.
def ms_since(t0_ns: int) -> float:
    """Return the precise elapsed time in milliseconds since t0_ns."""
    return (time.perf_counter_ns() - t0_ns) / 1_000_000.0


# Context manager to log start, success, and failure messages with elapsed duration.
@contextmanager
def log_timer(msg: str, logger: logging.Logger | None = None, **ctx):
    """
    Log a start/ok/failed message with elapsed time.
    Keeps logging consistent across modules.

    Usage:
        with log_timer("discover-columns", xml=path):
            ...
    """
    log = logger or logging.getLogger(__name__)
    t0 = time.perf_counter()
    if ctx:
        log.info("%s start %s", msg, ctx)
    else:
        log.info("%s start", msg)
    try:
        yield
    except Exception:
        dt = time.perf_counter() - t0
        if ctx:
            log.error("%s failed after %.3fs %s", msg, dt, ctx, exc_info=True)
        else:
            log.error("%s failed after %.3fs", msg, dt, exc_info=True)
        raise
    else:
        dt = time.perf_counter() - t0
        if ctx:
            log.info("%s ok in %.3fs %s", msg, dt, ctx)
        else:
            log.info("%s ok in %.3fs", msg, dt)
