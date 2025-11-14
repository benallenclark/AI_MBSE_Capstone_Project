from pathlib import Path

from app.flow.ingest.loader_duckdb import (
    ingest_xml as _ingest,
)
from app.infra.core.jobs_db import update_status


def run(xml_path: Path, *, model_id: str | None = None) -> dict:
    # after ingest
    update_status(job_id, status="running", progress=10, message="Ingest complete")
    return _ingest(xml_path, model_id=model_id, overwrite=False)
