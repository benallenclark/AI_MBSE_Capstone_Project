# app/api/v1/rag_stream.py
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

# Business logic lives in app.rag.service;
# this module only frames SSE output.
from app.rag.service import ask_stream

# v1 RAG streaming namespace:
# - Mounted under /v1 in app.main.
# - SSE endpoint emits incremental LLM deltas.
router = APIRouter()
logger = logging.getLogger(__name__)


# SSE endpoint:
# - Body: {"question": str, "model_id": str, "vendor": str, "version": str}
# - Stream: "data: {\"delta\": "..."}" lines and a final "event: done".
# - Keep handler async; generator itself must be sync for StreamingResponse.
@router.post("/ask_stream")
async def rag_ask_stream(req: Request):
    # Parse with basic guards; return 400 on missing keys
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

    # Wrap service.ask_stream() and format SSE frames.
    # Ensure chunks are JSON-escaped; avoid long blocking work inside this loop.
    def sse():
        token_count = 0
        for chunk in ask_stream(question, scope, cid=cid):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
            token_count += 1
            if token_count == 1:
                logger.info("rag.ask_stream first_token", extra={"cid": cid})
        logger.info("rag.ask_stream done", extra={"cid": cid, "tokens": token_count})
        yield "event: done\ndata: {}\n\n"

    # event-stream with proxy-friendly headers:
    # - "no-cache" prevents buffering by intermediaries
    # - "X-Accel-Buffering: no" disables nginx buffering for real-time delivery
    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
