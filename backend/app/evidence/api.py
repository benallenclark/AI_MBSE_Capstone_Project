# ------------------------------------------------------------
# Module: app/evidence/api.py
# Purpose: Single public entrypoint for emitting evidence from predicates.
# ------------------------------------------------------------

from pathlib import Path
from typing import Dict
from .types import PredicateOutput

# Keep builder details encapsulated; 
# predicates should only call emit_evidence().
from .builder import EvidenceBuilder

# Emit Evidence v2 documents to the per-model store.
# - model_dir: data/models/<id>
# - ctx: minimal provenance (model_id, vendor, version)
# - output: typed PredicateOutput (counts, facts, etc.)
# Returns: lightweight metadata for emitted docs (ids/titles) for UI/runner use.
def emit_evidence(model_dir: Path, ctx: Dict, output: PredicateOutput):
    # All predicates call this single function.
    return EvidenceBuilder(model_dir).emit(ctx, output)
