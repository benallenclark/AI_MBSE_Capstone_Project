# ------------------------------------------------------------
# Module: app/api/v1/schemas.py
# Purpose: /v1/models/{model_id} summary (public) + optional internals
# ------------------------------------------------------------
from __future__ import annotations
import json
from typing import Dict
from fastapi import APIRouter, HTTPException, Query
from app.core import paths

# Routers:
# - public_router: safe, stable contract for /v1/models/*
# - internal_router: debug-only; may expose filesystem paths (mount behind a flag)
public_router = APIRouter()
internal_router = APIRouter()

# Public summary:
# - Returns runner-produced summary.json verbatim.
# - If missing, emit a minimal stub so the UI can render "pending" state.
@public_router.get("/{model_id}")
def model_summary(model_id: str):
    p = paths.summary_json(model_id)
    if not p.exists():
        mdir = paths.model_dir(model_id)
        if not mdir.exists():
            raise HTTPException(status_code=404, detail="model_not_found")
        return {
            "schema_version": "1.0",
            "model_id": model_id,
            "maturity_level": None,
            "counts": {},
            "fingerprint": None,
            "created_at": (mdir.stat().st_mtime_ns // 1_000_000),
        }

    # Trust runner’s whitelist: do not add more evidence fields or file paths here.
    out = json.loads(p.read_text(encoding="utf-8")) or {}

    # IMPORTANT: Do NOT enrich with probe_id/title/ts_ms from evidence.jsonl.
    # The runner already whitelisted per-predicate keys: id, passed, counts, summary, source_tables.
    return out


# ---------- INTERNAL/DEBUG ONLY (not mounted unless EXPOSE_INTERNALS=True) ----------

# Internal: exposes absolute artifact paths for inspection.
# - Intentionally excluded from OpenAPI; mount only behind EXPOSE_INTERNALS.
@internal_router.get("/{model_id}/artifacts", include_in_schema=False)
def model_artifacts(model_id: str):
    mdir = paths.model_dir(model_id)
    if not mdir.exists():
        raise HTTPException(status_code=404, detail="model_not_found")
    return {
        "model_id": model_id,
        "artifacts": {
            "xml":            str(paths.xml_path(model_id).as_posix()),
            "duckdb":         str(paths.duckdb_path(model_id).as_posix()),
            "evidence_jsonl": str(paths.evidence_jsonl(model_id).as_posix()),
            "parquet_dir":    str(paths.parquet_dir(model_id).as_posix()),
            "rag_sqlite":     str(paths.rag_sqlite(model_id).as_posix()),
        },
    }

# Internal: returns up to `limit` JSONL rows from evidence (first N lines).
# - For debugging only; evidence shape may evolve across pipeline versions.
@internal_router.get("/{model_id}/evidence", include_in_schema=False)
def model_evidence(model_id: str, limit: int = Query(200, ge=1, le=1000)):
    p = paths.evidence_jsonl(model_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="evidence_not_found")
    rows = []
    with p.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            s = line.strip()
            if s:
                rows.append(json.loads(s))
    return {"model_id": model_id, "rows": rows, "limit": limit}

# Internal: latest 'summary' card per predicate (by ts_ms), with optional vendor/version filters.
# - Supports mixed evidence shapes: prefers probe_id, falls back to metadata.group_id suffix.
@internal_router.get("/{model_id}/summaries", include_in_schema=False)
def model_predicate_summaries(
    model_id: str,
    vendor: str = Query("", description="optional vendor filter"),
    version: str = Query("", description="optional version filter"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Internal: latest 'doc_type=summary' card per predicate from evidence.jsonl.
    Useful for debugging, not needed by frontend.
    """
    p = paths.evidence_jsonl(model_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="evidence_not_found")

    # Deduplicate by predicate id; keep the most recent (max ts_ms).
    latest_by_pid: Dict[str, dict] = {}
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            j = json.loads(s)
            if j.get("doc_type") != "summary":
                continue

            md = j.get("metadata") or {}
            if vendor and md.get("vendor") != vendor:
                continue
            if version and md.get("version") != version:
                continue

            pid = j.get("probe_id") or (md.get("group_id", "").split("/", 1)[-1])
            prev = latest_by_pid.get(pid)
            if prev is None or int(j.get("ts_ms", 0)) >= int(prev.get("ts_ms", 0)):
                latest_by_pid[pid] = j

    rows = sorted(
        latest_by_pid.values(),
        key=lambda r: (-int(r.get("ts_ms", 0)), r.get("probe_id", "")),
    )[:limit]
    return {"model_id": model_id, "rows": rows, "limit": limit}
