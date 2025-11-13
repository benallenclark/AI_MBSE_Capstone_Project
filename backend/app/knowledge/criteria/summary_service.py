# ------------------------------------------------------------
# Module: app/knowledge/criteria/summary_service.py
# Purpose: Unified read/write interface for model summaries.
# ------------------------------------------------------------

"""Single source of truth for reading, building, and
normalizing summaries — both for backend persistence and API serving."""

from __future__ import annotations

import json

from app.infra.core import paths
from app.interface.api.v1.models import EvidenceItem


def load_summary(model_id: str) -> dict:
    """Load and parse summary.json into a consistent dict."""
    summary_path = paths.summary_json(model_id)
    if not summary_path.exists():
        raise FileNotFoundError(f"summary_not_found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def parse_summary_to_evidence(summary: dict) -> list[EvidenceItem]:
    """Convert summary JSON into EvidenceItem objects."""
    results = summary.get("results") or []
    return [
        EvidenceItem(
            predicate=str(r.get("id", "")),
            passed=bool(r.get("passed", False)),
            details=r.get("details") or {},
        )
        for r in results
    ]


def get_summary_for_api(model_id: str) -> dict:
    """Convenience: full in-memory summary object for API responses."""
    data = load_summary(model_id)
    evidence = parse_summary_to_evidence(data)
    levels = data.get("levels", {})
    total = len(evidence)
    passed = sum(1 for e in evidence if e.passed)
    failed = total - passed

    model_meta = data.get("model", {})

    return {
        "schema_version": data.get("schema_version", "1.0"),
        "model_id": model_id,
        "model": {
            "vendor": model_meta.get("vendor", ""),
            "version": model_meta.get("version", ""),
        },
        "maturity_level": data.get("maturity_level", 0),
        "counts": data.get("counts", {}),
        "fingerprint": data.get("fingerprint", ""),
        "levels": levels,
        "summary": {"total": total, "passed": passed, "failed": failed},
        "results": evidence,
    }
