# ------------------------------------------------------------
# Module: app/api/v1/analyze.py
# Purpose: Synchronous dev analysis and async upload→job endpoints.
# ------------------------------------------------------------

"""Expose two analysis endpoints: a dev-only synchronous analyzer and an
async upload that schedules a background pipeline job. Keeps the controller
thin by delegating ingest and predicate execution to services.

Responsibilities
----------------
- Compute content-addressable IDs and persist model XML safely.
- Run sync predicate checks and summarize results deterministically.
- Launch background pipeline jobs from multipart uploads (202 + Location).
- Return typed contracts and caching headers for UI diffing.
"""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)

from app.api.v1.serializers.jobs import to_job_payload as _payload
from app.core import paths
from app.core.config import settings
from app.core.jobs_db import create_job, find_succeeded_by_sha, get_job
from app.services.analysis import (
    post_ingest_best_effort,
    run_pipeline_job,
    run_sync_predicates,
)
from app.services.jobs import get_or_synthesize_job_row, persist_model_xml
from app.utils.hashing import compute_sha256

from .models import (
    AnalyzeContract,
    AnalyzeRequest,
    Vendor,
)
from .serializers.analysis import analysis_fingerprint, normalize_results

router = APIRouter()
log = logging.getLogger("maturity.api.analyze")

# Guardrails:
# - Enforce max upload size early.
# - Ensure a stable model root exists before any per-model work.
MAX_UPLOAD_MB = settings.MAX_UPLOAD_MB

paths.MODELS_DIR.mkdir(parents=True, exist_ok=True)


# DEV-only sync analysis endpoint: ingest → predicates → return results.
@router.post("", response_model=AnalyzeContract, response_model_exclude_none=True)
def analyze(req: AnalyzeRequest, response: Response) -> AnalyzeContract:
    """
    Synchronous analysis (dev-only). For normal UI, use /upload + job polling.
    """
    model_sha = compute_sha256(req.xml_bytes)
    # Content-addressable ID: stable across identical files; used for idempotency.
    model_id = req.model_id or model_sha[:8]
    # Ensure XML exists (idempotent, no overwrite in sync path).
    xml_path = persist_model_xml(model_id, req.xml_bytes, overwrite=False)

    try:
        # Ingest + sync predicate run via service (keeps controller thin).
        level, evidence = run_sync_predicates(
            model_id=model_id,
            vendor=req.vendor.value,
            version=req.version,
            xml_path=xml_path,
        )
        # Kick off best-effort mirrors (kept, out of band).
        post_ingest_best_effort(model_id=model_id)

        # Flatten evidence into stable, API-facing results (typed, minimal, deterministic order).
        results = normalize_results(evidence)
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        # Stable fingerprint of normalized results (order-independent).
        fingerprint = analysis_fingerprint(results)

        if response is not None:
            # Expose model hash + analysis fingerprint for caching and diffing in the UI.
            response.headers["X-Model-SHA256"] = model_sha
            response.headers["X-Analysis-Fingerprint"] = fingerprint

        return AnalyzeContract(
            model={"vendor": req.vendor.value, "version": req.version},
            maturity_level=level,
            summary={"total": len(results), "passed": passed, "failed": failed},
            results=results,
        )

    # Input/validation errors → 400; unexpected failures → 500 with server-side logs.
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        log.exception("analysis_failed model_id=%s", model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
    finally:
        # nothing to close: DB connection is handled inside service layer
        pass


# Async upload endpoint: persist XML, create job, start background pipeline.
@router.post("/upload", status_code=202)
async def analyze_upload(
    response: Response,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    vendor: Vendor = Form(...),
    version: str = Form(...),
    model_id: str | None = Form(None),
):
    data = await file.read()
    # Hard reject oversize uploads at the edge (consistent with infrastructure limits).
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")

    sha = compute_sha256(data)

    # Reuse completed result if the same (sha, vendor, version) already succeeded
    # Idempotency: if (sha,vendor,version) already succeeded, skip to that job/result.
    existing = find_succeeded_by_sha(sha, vendor.value, version)
    if existing and existing.get("status") == "succeeded":
        job_id = existing["id"]
        # Always read the canonical row so progress/message/timings/types are correct
        row = get_job(job_id)
        if not row:
            # Extremely rare: index said yes but row missing; synthesize a safe row
            row = {  # type: ignore[assignment]
                "id": job_id,
                "sha256": sha,
                "model_id": existing["model_id"],
                "vendor": vendor.value,
                "version": version,
                "status": "succeeded",
                "progress": 100,
                "created_at": 0,
                "updated_at": 0,
            }
        response.headers["Location"] = f"/v1/jobs/{job_id}"
        return _payload(row)

    # Fresh job
    mid = model_id or sha[:8]
    job_id = create_job(sha, mid, vendor.value, version)

    # Persist upload (overwrite if client re-uploads same id)
    persist_model_xml(mid, data, overwrite=True)

    # Kick off the pipeline in background
    background.add_task(run_pipeline_job, job_id, mid)

    # Return a normalized snapshot (progress 0)
    row = get_or_synthesize_job_row(
        job_id,
        sha=sha,
        model_id=mid,
        vendor=vendor.value,
        version=version,
        fallback_status="queued",
    )
    response.headers["Location"] = f"/v1/jobs/{job_id}"
    return _payload(row)
