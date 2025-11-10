# ------------------------------------------------------------
# Module: app/api/v1/rag.py
# Purpose: RAG endpoints (ask + deterministic helpers)
# ------------------------------------------------------------
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

# Keep DB helpers minimally imported here to avoid coupling;
# complex retrieval stays in app.rag.service / app.rag.retrieve.
from app.rag.db import missing_ports
from app.rag.service import ask as rag_ask

# v1 RAG namespace:
# - Mounted under /v1 in app.main.
# - Keep endpoints thin; push retrieval/LLM logic into app.rag.service.
router = APIRouter()
logger = logging.getLogger(__name__)


# Request schema for RAG:
# - `question` minimal length avoids empty FTS queries.
# - (Scope) model_id/vendor/version must match what's in the index.
#   Consider Vendor enum + version normalizer if drift becomes common.
class AskIn(BaseModel):
    question: str = Field(..., min_length=4)
    model_id: str
    vendor: str
    version: str


# RAG ask:
# - Thin wrapper over service.ask(question, scope) → returns answer/citations/meta.
# - Map known "bad scope/index" errors to 400; let unexpected errors surface as 500.
#   NOTE: FileExistsError is unusual here—prefer ValueError/RuntimeError from service.
@router.post("/ask")
def ask(in_: AskIn, request: Request):
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    scope = {"model_id": in_.model_id, "vendor": in_.vendor, "version": in_.version}
    try:
        logger.info(
            "rag.ask start",
            extra={
                "cid": cid,
                "model_id": in_.model_id,
                "vendor": in_.vendor,
                "version": in_.version,
                "q_len": len(in_.question),
            },
        )
        resp = rag_ask(in_.question, scope, cid=cid)  # pass cid downstream
        # Encourage service to include retrieval stats in meta
        logger.info("rag.ask done", extra={"cid": cid, "meta": resp.get("meta", {})})
        return resp
    except FileExistsError as e:
        logger.warning("rag.ask bad_scope", extra={"cid": cid, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("rag.ask error", extra={"cid": cid})
        raise


# Deterministic helper:
# - Direct DB-backed check (no LLM). Useful for UI drill-down and smoke tests.
# - Treat as provisional API; prefer a generic predicates endpoint long-term.
@router.post("/missing-ports")
def api_missing_ports(in_: AskIn, request: Request):
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    scope = {"model_id": in_.model_id, "vendor": in_.vendor, "version": in_.version}
    logger.info("rag.missing_ports start", extra={"cid": cid, **scope})
    items = missing_ports(scope)
    logger.info("rag.missing_ports done", extra={"cid": cid, "count": len(items)})
    return {"items": items, "meta": {"count": len(items)}}
