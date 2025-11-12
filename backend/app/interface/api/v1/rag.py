# ------------------------------------------------------------
# Module: app/api/v1/rag.py
# Purpose: Define REST endpoints for RAG question-answering and deterministic utilities
# ------------------------------------------------------------

"""
This module exposes the main RAG API endpoints under the `/v1` namespace.
It provides a standard synchronous `/ask` route for retrieving model responses
and a deterministic `/missing-ports` helper for DB-backed diagnostics.

Responsibilities
----------------
- Define and validate the RAG input schema
- Delegate core logic to `app.artifacts.rag.service` and `app.artifacts.rag.db`
- Handle correlation IDs and structured logging for traceability
- Map known exceptions to appropriate HTTP error responses
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.artifacts.rag.db import missing_ports
from app.artifacts.rag.service import ask as rag_ask

# Initialize router for RAG v1 endpoints
router = APIRouter()
logger = logging.getLogger(__name__)


# Define request schema for RAG queries
class AskIn(BaseModel):
    """Schema for incoming RAG query requests."""

    question: str = Field(..., min_length=4)
    model_id: str
    vendor: str
    version: str


# Handle /ask POST requests for synchronous RAG Q&A
@router.post("/ask")
def ask(in_: AskIn, request: Request):
    """Submit a RAG question and return the model's answer with citations and metadata."""
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


# Handle /missing-ports POST requests for deterministic data validation
def api_missing_ports(in_: AskIn, request: Request):
    """Return missing port data for a given RAG index scope (no LLM inference)."""
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    scope = {"model_id": in_.model_id, "vendor": in_.vendor, "version": in_.version}
    logger.info("rag.missing_ports start", extra={"cid": cid, **scope})
    items = missing_ports(scope)
    logger.info("rag.missing_ports done", extra={"cid": cid, "count": len(items)})
    return {"items": items, "meta": {"count": len(items)}}
