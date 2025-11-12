# ------------------------------------------------------------
# Module: backend/app/ingest/types.py
# Purpose: Define typed structures for ingestion result metadata.
# ------------------------------------------------------------

"""Typed definitions representing results of an ingestion process.

Provides a structured contract for downstream components to interact
with normalized ingestion outputs and related metadata.

Responsibilities
----------------
- Define a clear data contract for ingestion results.
- Represent file paths and metadata for DuckDB, JSONL, and Parquet outputs.
- Support static typing and IDE autocompletion for ingestion workflows.
"""

from typing import TypedDict


class IngestResult(TypedDict):
    """Structured representation of ingestion output metadata."""

    model_id: str
    duckdb_path: str
    jsonl_dir: str
    parquet_dir: str
    tables: dict[str, int]
