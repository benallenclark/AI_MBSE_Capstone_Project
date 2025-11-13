# ------------------------------------------------------------
# Module: app/knowledge/criteria/build_summary.py
# Purpose: Aggregate predicate evidence into summary dicts.
# Note: This module performs pure aggregation only.
# It should not do any I/O — summary_service or runner handle persistence.
# ------------------------------------------------------------

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.interface.api.v1.models import EvidenceItem


def build_summary_dict(
    model_id: str,
    vendor: str,
    version: str,
    maturity_level: int,
    evidence: list[EvidenceItem],
    levels: dict[str, Any],
    evidence_docs: int = 0,
) -> dict[str, Any]:
    """Constructs a deterministic summary dict for writing to summary.json."""
    fingerprint = compute_fingerprint(evidence)
    total = len(evidence)
    passed = sum(1 for e in evidence if e.passed)
    failed = total - passed

    return {
        "schema_version": "1.0",
        "model_id": model_id,
        "model": {"vendor": vendor, "version": version},
        "maturity_level": maturity_level,
        "counts": {
            "predicates_total": total,
            "predicates_passed": passed,
            "predicates_failed": failed,
            "evidence_docs": evidence_docs,
        },
        "fingerprint": fingerprint,
        "levels": levels,
    }


def compute_fingerprint(evidence: list[EvidenceItem]) -> str:
    """Stable fingerprint based on predicate IDs, pass/fail, and detail keys."""
    fp_src = [
        {
            "id": e.predicate,
            "passed": bool(e.passed),
            "keys": sorted(list((e.details or {}).keys())),
        }
        for e in sorted(evidence, key=lambda x: (x.predicate or ""))
    ]
    return hashlib.sha256(
        json.dumps(fp_src, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
