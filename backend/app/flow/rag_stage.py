from pathlib import Path

from app.artifacts.rag.build_index import build_rag_index
from app.infra.core import paths
from app.infra.core.jobs_db import update_status


def run(model_id: str) -> Path:
    # done
    update_status(job_id, status="succeeded", progress=100, message="Done")
    return build_rag_index(paths.evidence_jsonl(model_id))
