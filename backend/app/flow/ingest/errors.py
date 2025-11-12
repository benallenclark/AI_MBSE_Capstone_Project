# ------------------------------------------------------------
# Module: backend/app/ingest/exceptions.py
# Purpose: Define typed ingest exceptions for clear, fail-fast error handling.
# ------------------------------------------------------------

"""Exception types for the ingest layer.

These provide specific, readable errors for common failure modes and keep the
core flow simple to reason about.

Responsibilities
----------------
- Provide a base `IngestError` for catch-all handling.
- Surface file write/rotation failures as `FileWriteError`.
- Surface DuckDB connection/statement failures as `DuckDBError`.
- Keep error taxonomy small and focused.
"""


class IngestError(Exception):
    """Base class for ingest failures."""


class FileWriteError(IngestError):
    """Raised on JSONL write/rotate failures."""


class DuckDBError(IngestError):
    """Raised on DuckDB connection/statement failures."""
