# ------------------------------------------------------------
# Module: app/api/v1/schemas.py
# Purpose: GET /v1/models/{model_id} → AnalyzeContract (final UI shape)
# ------------------------------------------------------------
from __future__ import annotations

import logging

import duckdb
from fastapi import APIRouter, HTTPException, Response

from app.api.v1.models import AnalyzeContract, PredicateResult
from app.core import paths
from app.core.config import settings
from app.core.jobs_db import _connect as _jobs_connect
from app.criteria.protocols import Context
from app.criteria.runner import run_predicates

public_router = APIRouter()
log = logging.getLogger("maturity.api.models")


def _latest_job_row(model_id: str) -> dict | None:
    con = _jobs_connect()
    cur = con.execute(
        "SELECT * FROM jobs WHERE model_id=? ORDER BY updated_at DESC LIMIT 1",
        (model_id,),
    )
    row = cur.fetchone()
    cols = [c[0] for c in cur.description] if cur.description else []
    con.close()
    return dict(zip(cols, row, strict=False)) if row else None


def _coerce_maturity_level(level_obj) -> int:
    """
    Accept:
      - int            -> 1
      - '1/3' (str)    -> 1
      - (1, 3)/[1, 3]  -> 1
    """
    if isinstance(level_obj, int):
        return level_obj
    if isinstance(level_obj, (tuple, list)) and level_obj:
        return int(level_obj[0])
    if isinstance(level_obj, str):
        return int(level_obj.split("/", 1)[0])
    raise ValueError(f"unsupported maturity level type: {type(level_obj).__name__}")


def _normalize_results(
    evidence: list, include_evidence: bool = False
) -> list[PredicateResult]:
    out: list[PredicateResult] = []
    for e in evidence:
        pid = e.predicate
        try:
            mml = int(pid.split(":")[0].split("_")[1])
        except Exception:
            mml = 0
        # Guard & copy details; redact heavy/private fields before returning to the frontend.
        raw_details = e.details if isinstance(getattr(e, "details", None), dict) else {}
        details = dict(raw_details)  # shallow copy so we don't mutate the source
        if not include_evidence:
            # Never expose raw evidence in the model summary payload by default.
            # (We keep it on disk for audits/RAG but do not send to the client.)
            details.pop("evidence", None)
            details.pop("source_tables", None)
            details.pop("probe_id", None)
            details.pop("mml", None)
            details.pop("passed", None)
            # If you want a UI hint, uncomment:
            # details["evidence_redacted"] = True
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


@public_router.get(
    "/{model_id}",
    response_model=AnalyzeContract,
    response_model_exclude_none=True,
)
def read_model(model_id: str, response: Response) -> AnalyzeContract:
    model_dir = paths.model_dir(model_id)
    if not model_dir.exists():
        raise HTTPException(status_code=404, detail="model_not_found")

    job = _latest_job_row(model_id)
    if not job:
        raise HTTPException(status_code=404, detail="model_job_not_found")

    db_path = paths.duckdb_path(model_id)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="model_db_not_found")

    con = None
    try:
        con = duckdb.connect(str(db_path))
        con.execute("PRAGMA enable_object_cache=true;")
        ctx = Context(
            vendor=str(job["vendor"]),
            version=str(job["version"]),
            model_dir=model_dir,
            model_id=model_id,
            output_root=paths.MODELS_DIR,
        )

        level_obj, evidence, _levels = run_predicates(con, ctx)
        maturity_level = _coerce_maturity_level(level_obj)

        results = _normalize_results(evidence)
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        return AnalyzeContract(
            schema_version=getattr(settings, "CONTRACT_SCHEMA_VERSION", "1.0"),
            model={"vendor": str(job["vendor"]), "version": str(job["version"])},
            maturity_level=int(maturity_level),
            summary={"total": int(total), "passed": int(passed), "failed": int(failed)},
            results=results,
        )

    except ValueError as e:
        # This is what triggers your 400; now it will be descriptive
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        log.exception("read_model_failed model_id=%s", model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
    finally:
        try:
            if con is not None:
                con.close()
        except Exception:
            log.warning("db_close_failed model_id=%s", model_id, exc_info=True)
