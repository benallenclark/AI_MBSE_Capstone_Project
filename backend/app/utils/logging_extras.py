# ------------------------------------------------------------
# Module: app/utils/logging_extras.py
# Purpose: Provide a helper for contextual logging with correlation IDs.
# ------------------------------------------------------------

"""Utility for creating logger adapters that attach contextual identifiers.

Wraps standard Python loggers with optional correlation ID context, enabling
traceable structured logs across async or multi-request flows.

Responsibilities
----------------
- Provide a simple adapter that adds correlation IDs to log records.
- Preserve full compatibility with the standard logging API.
- Support optional (or missing) correlation IDs gracefully.
- Simplify structured logging setup for services and background tasks.

Notes
-----
- Use this helper when logs need to be correlated per request or job.
- When `cid` is None, a plain logger is returned with no extra metadata.
"""

import logging


def log_adapter(logger: logging.Logger, cid: str | None) -> logging.LoggerAdapter:
    """Return a `LoggerAdapter` that injects an optional correlation ID.

    Parameters
    ----------
    logger : logging.Logger
        The base logger to wrap.
    cid : str | None
        Correlation or context ID (e.g., request ID, job ID). If None, no extra field is added.

    Returns
    -------
    logging.LoggerAdapter
        A logger adapter that preserves standard logging methods but includes `cid` in `extra`.

    Example
    -------
    >>> log = log_adapter(logging.getLogger(__name__), cid="abc123")
    >>> log.info("starting process")
    # emits: {"message": "starting process", "cid": "abc123"}
    """
    return logging.LoggerAdapter(logger, extra={"cid": cid} if cid else {})
