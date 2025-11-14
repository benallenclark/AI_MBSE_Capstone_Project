from pathlib import Path
from typing import Any

from app.artifacts.intelligence.cards.assembler import EvidenceBuilder
from app.infra.core.jobs_db import update_status


def run(model_dir: Path, *, ctx: dict[str, Any], predicate_output: Any):
    eb = EvidenceBuilder(model_dir)

    # after evidence build
    update_status(job_id, status="running", progress=60, message="Evidence built")
    return eb.emit(ctx, predicate_output)
