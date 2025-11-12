# ------------------------------------------------------------
# Module: app/rag/service.py
# Purpose: Orchestrate retrieval, prompt building, and LLM calls (sync/stream) with safe fallbacks.
# ------------------------------------------------------------

"""RAG service coordinating evidence retrieval, prompt construction, and LLM invocation.

Provides sync and streaming ask flows with structured logging, safe fallbacks on
errors, and citation assembly for downstream consumers.

Responsibilities
----------------
- Retrieve evidence cards based on a question and scope.
- Build prompts from questions and retrieved cards.
- Call the configured LLM client (non-stream and stream) with logging and fallbacks.
- Return answers with citations and helpful hints when retrieval is empty.
- Capture timing/metadata for observability.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator

from app.core.config import settings
from app.rag.client.ollama_client import OllamaClient
from app.rag.client.protocols import LLMClient
from app.rag.prompts import build_prompt, simple_summarize
from app.rag.retrieve import retrieve
from app.rag.retrieve import retrieve as _retrieve
from app.rag.types import AskResult, Citation
from app.utils.logging_extras import log_adapter

# module logger (structured logs via extra=...)
logger = logging.getLogger(__name__)


# Orchestrates retrieve → prompt → LLM call. Returns {"answer", "citations", ...meta}.
# On LLM failure, returns a warning + a deterministic summary so UX doesn’t dead-end.
def ask(
    question: str,
    scope: dict,
    *,
    cid: str | None = None,
    client: LLMClient | None = None,
    retrieve_fn=_retrieve,
) -> AskResult:
    """
    Retrieve → build prompt → call LLM (non-stream) → return full answer + citations.
    """
    lad = log_adapter(logger, cid)
    t0 = time.perf_counter()
    lad.info(
        "retrieval.start",
        extra={**scope, "k": settings.RAG_TOP_K, "q_len": len(question)},
    )
    cards = retrieve_fn(question, scope, k=settings.RAG_TOP_K)
    lad.info(
        "retrieval.done",
        extra={
            "retrieved": len(cards),
            "dur_ms": int((time.perf_counter() - t0) * 1000),
        },
    )
    meta: dict = {
        "retrieved": len(cards),
        **scope,
        "model": settings.GEN_MODEL,
        "provider": settings.LLM_PROVIDER,
    }

    if not cards:
        lad.warning("retrieval.empty", extra={**scope, "q": question[:80]})
        # Diagnostic probe: try without scope to detect scope mismatch vs empty index.
        # Non-fatal probe to improve UX
        t_probe = time.perf_counter()
        try:
            probe_cards = retrieve_fn(question, {}, k=3)
        except Exception as e:
            probe_cards = []
            lad.error("retrieval.probe.error", extra={"error": str(e)[:200]})
        finally:
            lad.info(
                "retrieval.probe",
                extra={
                    "retrieved": len(probe_cards),
                    "dur_ms": int((time.perf_counter() - t_probe) * 1000),
                },
            )

        if probe_cards:
            hint = "Selected scope likely excludes relevant docs. Clear scope or pick a different package/diagram."
        else:
            hint = "Index may be empty or not selected. Verify per-model rag.sqlite and model_id routing."

        return {
            "answer": f"No evidence found for the selected scope.\n\nHint: {hint}",
            "citations": [],
            **meta,
        }

    prompt = build_prompt(question, cards)
    lad.debug(
        "prompt.built", extra={"chars": len(prompt), "cards_used": min(len(cards), 8)}
    )
    client = client or OllamaClient.from_settings(settings, lad)
    try:
        t1 = time.perf_counter()
        text = client.generate(prompt)
        lad.info(
            "llm.answer.done",
            extra={
                "dur_ms": int((time.perf_counter() - t1) * 1000),
                "empty": int(not bool(text.strip())),
            },
        )
        if not text.strip():
            raise RuntimeError("Empty response from LLM")
    except Exception as e:
        lad.exception("llm.answer.error")
        text = f"[warn] LLM call failed: {e}\n\n" + simple_summarize(cards)

    citations: list[Citation] = [
        {"doc_id": c.get("doc_id"), "title": c.get("title")} for c in cards[:10]
    ]
    return {"answer": text, "citations": citations, **meta}


# ----------------------------- #
# Public API: ask_stream (yields deltas)
# ----------------------------- #


def ask_stream(
    question: str,
    scope: dict,
    *,
    cid: str | None = None,
    client: LLMClient | None = None,
    retrieve_fn=_retrieve,
) -> Generator[str, None, None]:
    """
    Retrieve → build prompt → stream from LLM.
    Yields text deltas (strings). Your FastAPI route can wrap this as:
      - SSE:   yield f"data: {json.dumps({'delta': chunk})}\\n\\n"
      - NDJSON: yield json.dumps({'delta': chunk}) + "\\n"
    """
    lad = log_adapter(logger, cid)
    t0 = time.perf_counter()
    lad.info(
        "retrieval.start",
        extra={
            **scope,
            "k": settings.RAG_TOP_K,
            "q_len": len(question),
            "stream": True,
        },
    )
    cards = retrieve_fn(question, scope, k=settings.RAG_TOP_K)
    lad.info(
        "retrieval.done",
        extra={
            "retrieved": len(cards),
            "dur_ms": int((time.perf_counter() - t0) * 1000),
            "stream": True,
        },
    )

    if not cards:
        lad.warning("retrieval.empty", extra={**scope, "stream": True})
        # Probe (non-fatal): try without scope to provide a helpful hint.
        try:
            probe = retrieve(question, {}, k=3)
        except Exception:
            probe = []
        if probe:
            yield "No evidence for current scope. Try clearing scope or selecting a different package/diagram."
        else:
            yield "No evidence found. Check that the per-model RAG index exists and that retrieval targets it."
        return

    prompt = build_prompt(question, cards)

    # Stream tokens; if the provider fails, yield a single fallback summary
    yielded_any = False
    client = client or OllamaClient.from_settings(settings, lad)
    try:
        for chunk in client.stream(prompt):
            yielded_any = True
            if chunk:
                yield chunk
    except Exception as e:
        lad.exception("llm.stream.error")
        # Emit one warning token, then a compact summary
        yield f"[warn] LLM stream failed: {e}\n"
        yield simple_summarize(cards)
        return

    if not yielded_any:
        lad.warning("llm.stream.empty")
        # Provider returned nothing; give user something useful
        yield simple_summarize(cards)
