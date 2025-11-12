from pathlib import Path
from typing import Any

from app.artifacts.evidence.assembler import EvidenceBuilder


def run(model_dir: Path, *, ctx: dict[str, Any], predicate_output: Any):
    eb = EvidenceBuilder(model_dir)
    return eb.emit(ctx, predicate_output)
