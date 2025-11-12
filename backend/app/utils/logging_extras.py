# ------------------------------------------------------------
# Module: app/utils/logging_extras.py
# Purpose: Provide a helper for contextual logging with correlation IDs.
# ------------------------------------------------------------

"""Utility for creating logger adapters that attach contextual identifiers.

This module wraps standard loggers with optional correlation ID context,
enabling traceable logs across asynchronous or multi-request flows.

Responsibilities
----------------
- Provide a simple adapter to attach correlation IDs to log records.
- Maintain compatibility with the standard Python logging API.
- Support optional context (no CID when absent).
- Simplify structured and contextualized logging setup.
"""

import logging


# Create a LoggerAdapter that attaches an optional correlation ID to each log record.
def log_adapter(logger: logging.Logger, cid: str | None) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logger, extra={"cid": cid} if cid else {})
