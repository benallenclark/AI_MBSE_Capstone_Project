# ------------------------------------------------------------
# Module: app/evidence/api.py
# Purpose: Single public entrypoint for emitting evidence from predicates.
# ------------------------------------------------------------

"""Unified entrypoint for predicates to emit Evidence v2 documents.

Responsibilities
----------------
- Provide a single, stable interface for all predicates to write evidence.
- Hide implementation details of the underlying EvidenceBuilder.
- Ensure consistent evidence formatting and storage in the per-model directory.
"""

from pathlib import Path

from .assembler import EvidenceBuilder
from .types import PredicateOutput


def emit_evidence(model_dir: Path, ctx: dict, output: PredicateOutput):
    """Emit Evidence v2 documents to a model’s evidence store.

    Parameters
    ----------
    model_dir : Path
        Root directory for this model (e.g., `data/models/<id>`).
    ctx : dict
        Minimal provenance context (typically includes `model_id`, `vendor`, `version`).
    output : PredicateOutput
        Structured predicate results (facts, counts, and metadata).

    Returns
    -------
    dict
        Lightweight metadata about emitted evidence (e.g., IDs and titles) for
        downstream consumption by the UI or runner.

    Notes
    -----
    - This is the only function predicates should call to write evidence.
    - Keeps builder details private for consistent versioned output.
    """
    return EvidenceBuilder(model_dir).emit(ctx, output)
