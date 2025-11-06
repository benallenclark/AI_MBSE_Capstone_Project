# ------------------------------------------------------------
# Module: app/api/v1/rag.py
# Purpose: RAG endpoints (ask + deterministic helpers)
# ------------------------------------------------------------
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.rag.service import ask as rag_ask

# Keep DB helpers minimally imported here to avoid coupling;
# complex retrieval stays in app.rag.service / app.rag.retrieve.
from app.rag.db import missing_ports

# v1 RAG namespace:
# - Mounted under /v1 in app.main.
# - Keep endpoints thin; push retrieval/LLM logic into app.rag.service.
router = APIRouter()

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
def ask(in_: AskIn):
    scope = {"model_id": in_.model_id, "vendor": in_.vendor, "version": in_.version}
    try:
        return rag_ask(in_.question, scope)
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Deterministic helper:
# - Direct DB-backed check (no LLM). Useful for UI drill-down and smoke tests.
# - Treat as provisional API; prefer a generic predicates endpoint long-term.
@router.post("/missing-ports")
def api_missing_ports(in_: AskIn):
    scope = {"model_id": in_.model_id, "vendor": in_.vendor, "version": in_.version}
    return {"items": missing_ports(scope)}
