# ------------------------------------------------------------
# Module: app/api/v1/rag_stream.py
# Purpose: Expose a FastAPI SSE endpoint for real-time RAG LLM streaming responses
# ------------------------------------------------------------

"""
This module provides a FastAPI endpoint that streams incremental LLM responses
as Server-Sent Events (SSE). It serves as a thin adapter layer around the core
RAG logic in `app.rag.service.ask_stream`.

Responsibilities
----------------
- Parse and validate incoming POST requests for RAG queries
- Stream tokenized model outputs using Server-Sent Events
- Manage correlation IDs and structured logging
- Apply proxy-safe headers to ensure real-time delivery
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.rag.service import ask_stream

# Initialize router for v1 RAG streaming endpoints
router = APIRouter()
logger = logging.getLogger(__name__)


# Handle /ask_stream POST requests for real-time RAG output
@router.post("/ask_stream")
async def rag_ask_stream(req: Request):
    # Parse request body and validate required fields
    body = await req.json()
    if "question" not in body:
        raise HTTPException(status_code=400, detail="missing 'question'")
    for k in ("model_id", "vendor", "version"):
        if k not in body:
            raise HTTPException(status_code=400, detail=f"missing '{k}'")
    question = body["question"]
    scope = {k: body[k] for k in ("model_id", "vendor", "version")}
    cid = req.headers.get("x-correlation-id") or str(uuid.uuid4())
    logger.info(
        "rag.ask_stream start",
        extra={"cid": cid, **scope, "q_len": len(question)},
    )

    # Generator function that wraps ask_stream() and yields SSE frames
    def sse():
        token_count = 0
        for chunk in ask_stream(question, scope, cid=cid):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
            token_count += 1
            if token_count == 1:
                logger.info("rag.ask_stream first_token", extra={"cid": cid})
        logger.info("rag.ask_stream done", extra={"cid": cid, "tokens": token_count})
        yield "event: done\ndata: {}\n\n"

    # Return streaming response with SSE headers for real-time delivery
    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
