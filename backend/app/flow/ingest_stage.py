from pathlib import Path

from app.flow.ingest.loader_duckdb import (
    ingest_xml as _ingest,  # keep ingest where it is
)


def run(xml_path: Path, *, model_id: str | None = None) -> dict:
    return _ingest(xml_path, model_id=model_id, overwrite=False)
