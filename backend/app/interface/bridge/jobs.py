# ------------------------------------------------------------
# Module: app/services/jobs.py
# Purpose: Manage job metadata and ensure model XML persistence.
# ------------------------------------------------------------

"""Utility functions for handling job records and model XML persistence.

Ensures stable access to job metadata and consistent on-disk storage
of model XML files within the models directory.

Responsibilities
----------------
- Persist and manage model XML files on disk.
- Retrieve or synthesize job rows for consistent API responses.
- Provide predictable fallback data shapes when database rows are missing.
- Support idempotent file writes and safe job metadata retrieval.

Notes
-----
- All synthesized job rows follow the same shape as those from the DB.
- `persist_model_xml` creates directories as needed and is idempotent unless
  explicitly told to overwrite.
"""

from __future__ import annotations

from pathlib import Path

from app.infra.core import paths
from app.infra.core.jobs_db import get_job


# Write or ensure existence of a model XML file for a given model ID.
def persist_model_xml(model_id: str, data: bytes, *, overwrite: bool = False) -> Path:
    """
    Ensure the model’s XML file exists under `data/models/<model_id>/model.xml`.

    Parameters
    ----------
    model_id : str
        Unique model identifier.
    data : bytes
        Raw XML content to write.
    overwrite : bool, optional
        If True, replaces any existing XML file. Defaults to False.

    Returns
    -------
    Path
        The path to the persisted XML file.

    Notes
    -----
    - Creates parent directories if missing.
    - Safe to call multiple times (idempotent unless `overwrite=True`).
    """
    model_dir = paths.model_dir(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)
    xml_path = model_dir / "model.xml"

    if overwrite or not xml_path.exists():
        xml_path.write_bytes(data)
    return xml_path


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
    Return an existing job record, or synthesize a default one if missing.

    Parameters
    ----------
    job_id : str
        The job identifier to retrieve.
    sha : str
        Hash of the model file (used when synthesizing).
    model_id : str
        Associated model identifier.
    vendor : str
        Model vendor name.
    version : str
        Model version or release tag.
    fallback_status : str
        Status to assign if no record exists (e.g. "succeeded", "failed").

    Returns
    -------
    dict
        A full job record (either from DB or synthesized for consistency).

    Notes
    -----
    - Synthesized rows maintain shape compatibility with `get_job` outputs.
    - Progress defaults to 100% if status is `"succeeded"`, else 0%.
    """
    row = get_job(job_id)
    if row:
        return row

    # Build a safe, shape-stable fallback row for missing jobs.
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
