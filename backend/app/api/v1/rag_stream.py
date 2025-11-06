# app/api/v1/rag_stream.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

# Business logic lives in app.rag.service; 
# this module only frames SSE output.
from app.rag.service import ask_stream

# v1 RAG streaming namespace:
# - Mounted under /v1 in app.main.
# - SSE endpoint emits incremental LLM deltas.
router = APIRouter()

# SSE endpoint:
# - Body: {"question": str, "model_id": str, "vendor": str, "version": str}
# - Stream: "data: {\"delta\": "..."}" lines and a final "event: done".
# - Keep handler async; generator itself must be sync for StreamingResponse.
@router.post("/ask_stream")
async def rag_ask_stream(req: Request):
    # Minimal parsing by design; 
    # consider a Pydantic model + 400 on missing keys
    body = await req.json()
    question = body["question"]
    scope = {k: body[k] for k in ("model_id", "vendor", "version") if k in body}

    # Wrap service.ask_stream() and format SSE frames.
    # Ensure chunks are JSON-escaped; avoid long blocking work inside this loop.
    def sse():
        for chunk in ask_stream(question, scope):
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "event: done\ndata: {}\n\n"

    # event-stream with proxy-friendly headers:
    # - "no-cache" prevents buffering by intermediaries
    # - "X-Accel-Buffering: no" disables nginx buffering for real-time delivery
    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
