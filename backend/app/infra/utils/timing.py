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

Notes
-----
- Uses `time.perf_counter()` / `perf_counter_ns()` for monotonic, high-resolution timing.
- Designed for operational observability (not benchmarking precision).
- Safe for concurrent use in multithreaded environments.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager


def now_ns() -> int:
    """Return the current high-resolution timestamp in nanoseconds.

    Notes
    -----
    - Based on `time.perf_counter_ns()` (monotonic and precise).
    - Use for duration deltas, not for wall-clock time.
    """
    return time.perf_counter_ns()


def ms_since(t0_ns: int) -> float:
    """Return elapsed milliseconds since the given start time (ns).

    Parameters
    ----------
    t0_ns : int
        Start time from `now_ns()`.

    Returns
    -------
    float
        Elapsed time in milliseconds.
    """
    return (time.perf_counter_ns() - t0_ns) / 1_000_000.0


@contextmanager
def log_timer(msg: str, logger: logging.Logger | None = None, **ctx):
    """Context manager for timing and structured logging around a code block.

    Logs start, success, and failure messages with consistent formatting and duration tracking.

    Parameters
    ----------
    msg : str
        Operation name or descriptive label for the timed block.
    logger : logging.Logger | None, optional
        Logger instance to use; defaults to module logger.
    **ctx : dict
        Optional key-value pairs to include in structured log output.

    Example
    -------
    >>> with log_timer("load-model", model_id="abc123"):
    ...     run_model_load()
    # emits:
    # load-model start {'model_id': 'abc123'}
    # load-model ok in 0.382s {'model_id': 'abc123'}

    Notes
    -----
    - Logs three stages: `start`, `ok`, and `failed`.
    - On exception, logs the error with `exc_info=True` before re-raising.
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
