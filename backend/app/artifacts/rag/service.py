# ------------------------------------------------------------
# Module: app/artifacts/rag/service.py
# Purpose: Orchestrate retrieve → build prompt → LLM (sync/stream) with fallbacks.
# ------------------------------------------------------------

from __future__ import annotations

import logging
import time
from collections.abc import Iterable

from app.infra.core.config import settings
from app.infra.utils.logging_extras import log_adapter  # existing helper in your tree

from .client.ollama_client import OllamaClient
from .prompts import build_prompt
from .retrieve import retrieve as _retrieve
from .types import AskResult

log = logging.getLogger(__name__)


def ask(
    question: str,
    scope: dict,
    *,
    cid: str | None = None,
    client: OllamaClient | None = None,
    retrieve_fn=_retrieve,
) -> AskResult:
    """Sync ask: retrieve cards → build prompt → generate; emit hints on empty."""
    lad = log_adapter(log, cid)
    t0 = time.perf_counter()

    cards = retrieve_fn(question, scope, k=settings.RAG_TOP_K)
    meta = {"retrieved": len(cards), "model": "", "provider": "ollama"}

    if not cards:
        # helpful hint based on a probe without scope, same as you do today
        try:
            probe_cards = retrieve_fn(question, {}, k=3)
            hint = (
                "Selected scope likely excludes relevant docs. Clear scope or pick a different package/diagram."
                if probe_cards
                else "Index may be empty or not selected. Verify per-model rag.sqlite and model_id routing."
            )
        except Exception:
            hint = "Index may be empty or not selected. Verify per-model rag.sqlite and model_id routing."
        return {
            "answer": f"No evidence found for the selected scope.\n\nHint: {hint}",
            "citations": [],
            **meta,
        }

    # Build prompt from raw cards (prompts.build_prompt handles 'body' or 'body_text')
    prompt = build_prompt(question, cards)
    # Optional: keep a compact preview for logs
    # log.debug("context.preview=\n%s", pack_context(cards)[:400])
    log.debug("prompt.len=%d", len(prompt))
    client = client or OllamaClient.from_settings(settings, lad)

    try:
        answer = client.generate(prompt)
    except Exception as e:
        lad.exception("llm.generate.error")
        return {
            "answer": f"[warn] LLM error: {e}\n\n" + simple_summarize(cards),
            "citations": [],
            **meta,
        }

    return {"answer": answer, "citations": cards[:10], **meta, "model": client.model}


def ask_stream(
    question: str,
    scope: dict,
    *,
    cid: str | None = None,
    client: OllamaClient | None = None,
    retrieve_fn=_retrieve,
) -> Iterable[str]:
    """Streaming ask: same as ask(), but yields tokens; emits compact summary on error/empty."""
    lad = log_adapter(logger, cid)
    cards = retrieve_fn(question, scope, k=settings.RAG_TOP_K)

    if not cards:
        yield "No evidence found for the selected scope.\n\n"
        # best-effort hint (non-fatal)
        try:
            probe_cards = retrieve_fn(question, {}, k=3)
            hint = (
                "Selected scope likely excludes relevant docs. Clear scope or pick a different package/diagram."
                if probe_cards
                else "Index may be empty or not selected. Verify per-model rag.sqlite and model_id routing."
            )
        except Exception as e:
            hint = f"Probe failed: {e}"
        yield f"Hint: {hint}"
        return

    # build the same prompt used by non-streaming
    prompt = build_prompt(question, cards)
    # Optional preview
    # log.debug("context.preview=\n%s", pack_context(cards)[:400])

    client = client or OllamaClient.from_settings(settings, lad)

    yielded_any = False
    try:
        for chunk in client.stream(prompt):
            yielded_any = True
            if chunk:
                yield chunk
    except Exception as e:
        lad.exception("llm.stream.error")
        yield f"[warn] LLM stream failed: {e}\n"
        yield simple_summarize(cards)
        return

    if not yielded_any:
        lad.warning("llm.stream.empty")
        yield simple_summarize(cards)
