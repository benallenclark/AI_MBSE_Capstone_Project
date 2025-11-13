# ------------------------------------------------------------
# Module: app/knowledge/criteria/write_summary.py
# Purpose: Write summary.json and related outputs to disk.
# Note: Only responsible for persistence (summary.json, evidence.jsonl).
# Do not perform aggregation logic here.
# ------------------------------------------------------------

from __future__ import annotations

import json
from pathlib import Path

from app.infra.core import paths


def count_evidence_docs(model_id: str) -> int:
    """Count evidence lines in evidence.jsonl, if present."""
    ej = paths.evidence_jsonl(model_id)
    docs = 0
    try:
        with ej.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    docs += 1
    except FileNotFoundError:
        pass
    return docs


def write_summary_json(model_id: str, summary: dict) -> Path:
    """Write the final summary.json file to the model directory."""
    out_path = paths.summary_json(model_id)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return out_path
