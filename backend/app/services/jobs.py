# ------------------------------------------------------------
# Module: app/services/jobs.py
# Purpose: Manage job metadata and ensure model XML persistence.
# ------------------------------------------------------------

"""Utility functions for handling job records and model XML persistence.

This module ensures stable access to job information and guarantees that
model XML files are stored in a consistent location within the models directory.

Responsibilities
----------------
- Persist and manage model XML files on disk.
- Retrieve existing job rows from the database.
- Synthesize fallback job records for missing entries.
- Maintain consistent and predictable job data shapes.
"""

from __future__ import annotations

from pathlib import Path

from app.core import paths
from app.core.jobs_db import get_job


# Write or ensure existence of a model XML file for a given model ID.
def persist_model_xml(model_id: str, data: bytes, *, overwrite: bool = False) -> Path:
    """
    Ensure data/models/<model_id>/model.xml exists with the given bytes.
    Returns the XML Path. Idempotent unless overwrite=True.
    """
    model_dir = paths.model_dir(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)
    xml_path = model_dir / "model.xml"
    if overwrite or not xml_path.exists():
        xml_path.write_bytes(data)
    return xml_path


# Retrieve an existing job row or synthesize a default snapshot if missing.
def get_or_synthesize_job_row(
    job_id: str,
    *,
    sha: str,
    model_id: str,
    vendor: str,
    version: str,
    fallback_status: str,
):
    """
    Return canonical job row; synthesize a safe snapshot if missing (shape stable for API).
    """
    row = get_job(job_id)
    if row:
        return row
    return {  # type: ignore[return-value]
        "id": job_id,
        "sha256": sha,
        "model_id": model_id,
        "vendor": vendor,
        "version": version,
        "status": fallback_status,
        "progress": 100 if fallback_status == "succeeded" else 0,
        "created_at": 0,
        "updated_at": 0,
    }
