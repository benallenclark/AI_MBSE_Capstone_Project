# ------------------------------------------------------------
# Module: app/interface/api/v1/serializers/analysis.py
# Purpose: Pure, deterministic serialization of analysis results for API output.
# ------------------------------------------------------------

"""Normalize analysis evidence into compact API contracts and fingerprints.
This module transforms internal `EvidenceItem` objects into public-facing
`PredicateResult` records and computes a stable hash for change detection.

Responsibilities
----------------
- Convert `EvidenceItem` → `PredicateResult` for the API contract.
- Optionally redact heavy/sensitive fields from details.
- Preserve determinism and JSON-serializability of outputs.
- Produce an order-independent SHA-256 fingerprint for caching/dedup.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence

from ..models import EvidenceItem, PredicateResult


# Transform EvidenceItem → PredicateResult for the public API contract.
def normalize_results(
    evidence: Sequence[EvidenceItem],
    *,
    redact: bool = True,
) -> list[PredicateResult]:
    """Normalize evidence items into API-facing predicate results.

    Args:
        evidence: Sequence of `EvidenceItem` instances to transform.
        redact: Whether to remove sensitive or large internal fields.

    Returns:
        List of `PredicateResult` objects suitable for API serialization.

    Contract:
        - Handles malformed predicate IDs safely (`mml=0` fallback).
        - Deterministic and side-effect free.
    """
    out: list[PredicateResult] = []
    for e in evidence:
        pid = e.predicate
        try:
            # Extract tier level (MML) from predicate id like 'mml_1:some_check'
            mml = int(pid.split(":")[0].split("_")[1])
        except Exception:
            mml = 0
        # Defensive shallow copy: ensure details are a dict and isolate mutation.
        raw_details = e.details if isinstance(getattr(e, "details", None), dict) else {}
        details = dict(raw_details)

        # Redact fields that are unnecessary for frontend summary-display
        if redact:
            for k in ("evidence", "source_tables", "probe_id", "mml", "passed"):
                details.pop(k, None)
        out.append(
            PredicateResult(
                id=pid,
                mml=mml,
                passed=bool(e.passed),
                details=details,
                error=(str(e.error) if getattr(e, "error", None) else None),
            )
        )
    return out


# Compute an order-independent SHA-256 fingerprint of normalized results.
def analysis_fingerprint(results: Iterable[PredicateResult]) -> str:
    """Compute a stable, order-independent fingerprint for normalized results.

    Args:
        results: Iterable of `PredicateResult` objects (normalized form).

    Returns:
        A 64-character hexadecimal SHA-256 digest representing content deterministically.
    """
    payload = [
        r.model_dump(exclude_none=True)
        for r in sorted(results, key=lambda r: (r.mml, r.id))
    ]
    # The serialized structure must not depend on runtime ordering.
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = ["normalize_results", "analysis_fingerprint"]
