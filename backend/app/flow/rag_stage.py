from pathlib import Path

from app.artifacts.rag.build_index import build_rag_index
from app.infra.core import paths


def run(model_id: str) -> Path:
    return build_rag_index(paths.evidence_jsonl(model_id))
