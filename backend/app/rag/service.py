# ------------------------------------------------------------
# Module: app/rag/service.py
# Purpose: Retrieve evidence, build prompts, and
#          call Ollama (non-stream/stream) with safe defaults and fallback.
# ------------------------------------------------------------

from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator

import requests

from app.core.config import settings
from app.rag.retrieve import retrieve

# module logger (structured logs via extra=...)
logger = logging.getLogger(__name__)


def _log_adapter(cid: str | None = None) -> logging.LoggerAdapter:
    """Bind correlation id (cid) so every line can be joined across layers."""
    return logging.LoggerAdapter(logger, extra={"cid": cid} if cid else {})


# Normalizes user/config options to JSON-safe types and conservative defaults.
# Guards against bad strings (e.g., "0.2") and unbounded context windows that spike memory.
def _sanitize_ollama_options(
    opts: dict | None, *, lad: logging.LoggerAdapter | None = None
) -> dict:
    """
    Ensure options are JSON-serializable with correct numeric types and safe defaults.
    - Converts str -> float for temperature/top_p if needed
    - Clamps num_ctx to a conservative ceiling unless explicitly set smaller
    """
    opts = dict(opts or {})
    if "temperature" in opts and isinstance(opts["temperature"], str):
        try:
            opts["temperature"] = float(opts["temperature"])
        except ValueError:
            opts["temperature"] = 0.2
    if "top_p" in opts and isinstance(opts["top_p"], str):
        try:
            opts["top_p"] = float(opts["top_p"])
        except ValueError:
            opts["top_p"] = 0.95

    # Keep memory usage predictable while stabilizing
    default_ctx = 2048
    num_ctx = opts.get("num_ctx", default_ctx)
    try:
        num_ctx = int(num_ctx)
    except Exception:
        num_ctx = default_ctx

    # Caps context to avoid OOM on small hosts; opt-in upstream if you truly need larger windows.
    # Trade-off: smaller `num_ctx` → less past text but more stable memory.
    if num_ctx > 4096:
        num_ctx = 2048
    opts["num_ctx"] = num_ctx
    if lad:
        # log only safe, non-sensitive tuning knobs
        lad.debug(
            "ollama.options",
            extra={
                "num_ctx": num_ctx,
                "has_temp": "temperature" in opts,
                "has_top_p": "top_p" in opts,
            },
        )

    return opts


# Inputs: user question + top evidence cards; Output: a compact, citeable prompt string.
# Keep inputs sanitized—very large `cards` bodies will bloat prompts and slow generation.
def _build_prompt(question: str, cards: list[dict]) -> str:
    """
    Compose a compact prompt from top evidence cards.
    Keep it small; streaming is about responsiveness.
    """

    # Limit cards to a small N to stay within context;
    # increase only if you’ve measured quality vs. latency.
    N = 8
    parts: list[str] = []
    for c in cards[:N]:
        title = c.get("title") or c.get("doc_id") or "Card"
        body = c.get("body_text") or c.get("body") or ""
        parts.append(f"Title: {title}\nBody: {body}")

    context = "\n\n".join(parts)
    return (
        "You are an MBSE maturity assistant.\n\n"
        f"Question:\n{question}\n\n"
        "Evidence (cards):\n"
        f"{context}\n\n"
        "Respond with a brief, concrete answer that cites specific findings from the evidence above and suggests next steps."
    )


def _simple_summarize(cards: list[dict]) -> str:
    titles = [c.get("title") for c in cards if c.get("title")]
    head = f"Found {len(cards)} evidence cards in scope."
    if titles:
        head += " Example items:\n- " + "\n- ".join(titles[:5])
    return head + (
        "\n\nStart by fixing high-impact hygiene: type all ports, remove unused elements, "
        "add missing requirement links, and resolve duplicate names."
    )


def _ollama_base_url() -> str:
    # settings.OLLAMA may be a host or a bare port; normalize to http://host:port
    base = str(settings.OLLAMA)
    return base if base.startswith("http") else "http://localhost:11434"


def _is_ollama_oom(text: str) -> bool:
    msg = (text or "").lower()
    return (
        ("more system memory" in msg)
        or ("unable to load full model" in msg)
        or ("out of memory" in msg)
    )


# Returns the full model response or raises RuntimeError on failure.
# Side effects: network call to Ollama; caller should treat output as untrusted text.
def _call_llm(prompt: str, *, cid: str | None = None) -> str:
    """
    Call the configured LLM and return the full string response.
    Keeps provider branching contained here.
    """
    if settings.LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")

    lad = _log_adapter(cid)
    base = _ollama_base_url()
    primary_model = settings.GEN_MODEL
    fallback_model = getattr(settings, "FALLBACK_MODEL", "phi3:mini")

    def _generate(model_name: str) -> tuple[bool, str]:
        t0 = time.perf_counter()
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": _sanitize_ollama_options(
                getattr(settings, "ollama_options", {}), lad=lad
            ),
        }
        lad.info("llm.call", extra={"model": model_name})
        # 90s total timeout—slow or large generations may exceed this. Tune per deployment.
        # Errors bubble up as RuntimeError (below); include payload options in logs for diagnosis.
        r = requests.post(f"{base}/api/generate", json=payload, timeout=90)
        lad.info(
            "llm.call.done",
            extra={
                "model": model_name,
                "ok": r.ok,
                "status": r.status_code,
                "dur_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
        if not r.ok:
            return False, f"Ollama {r.status_code}: {r.text}"
        data = r.json()
        return True, (data.get("response") or "").strip()

    ok, resp = _generate(primary_model)
    if ok:
        return resp

    # Heuristic on error text; can misclassify.
    # Only one fallback attempt—subsequent failures propagate.
    if _is_ollama_oom(resp):
        lad.warning(
            "llm.fallback",
            extra={"reason": "oom", "from": primary_model, "to": fallback_model},
        )
        ok2, resp2 = _generate(fallback_model)
        if ok2:
            return resp2
        raise RuntimeError(f"[fallback failed] {resp2}")

    # Other errors: surface payload for observability
    raise RuntimeError(resp)


# Yields text chunks as they arrive; consumers should frame as SSE/NDJSON.
# Converts most failures into a single warning (and may try a tiny fallback model).
def _call_llm_stream(
    prompt: str, *, cid: str | None = None
) -> Generator[str, None, None]:
    """
    Stream tokens from the configured LLM via Ollama NDJSON.
    Yields text deltas. Caller frames as SSE/NDJSON.
    """
    if settings.LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")

    lad = _log_adapter(cid)
    base = _ollama_base_url()
    primary_model = settings.GEN_MODEL
    fallback_model = getattr(
        settings, "FALLBACK_MODEL", "qwen2.5:0.5b-instruct-q4_0"
    )  # tiny & reliable

    def stream_model(model_name: str) -> Generator[str, None, None]:
        t0 = time.perf_counter()
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": _sanitize_ollama_options(
                getattr(settings, "ollama_options", {}), lad=lad
            ),
        }

        # 5s connect timeout, infinite read—hung servers can stall forever.
        # Add a read timeout if needed.
        # Parses NDJSON per line; non-JSON lines are ignored for resilience.
        with requests.post(
            f"{base}/api/generate", json=payload, stream=True, timeout=(5, None)
        ) as r:
            if not r.ok:
                # Surface body so caller can decide about fallback
                lad.info(
                    "llm.stream.open",
                    extra={
                        "model": model_name,
                        "ok": False,
                        "status": r.status_code,
                        "dur_ms": int((time.perf_counter() - t0) * 1000),
                    },
                )
                raise RuntimeError(f"Ollama {r.status_code}: {r.text}")
            lad.info(
                "llm.stream.open",
                extra={
                    "model": model_name,
                    "ok": True,
                    "status": r.status_code,
                    "dur_ms": int((time.perf_counter() - t0) * 1000),
                },
            )
            token_count = 0
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = obj.get("response")
                if chunk:
                    if token_count == 0:
                        lad.info("llm.stream.first_token", extra={"model": model_name})
                    token_count += 1
                    yield chunk
                if obj.get("done"):
                    lad.info(
                        "llm.stream.done",
                        extra={"model": model_name, "tokens": token_count},
                    )
                    break

    # Try primary
    try:
        yield from stream_model(primary_model)
        return
    except Exception as e:
        msg = str(e)
        if (
            _is_ollama_oom(msg)
            or "model not found" in msg.lower()
            or "no such file" in msg.lower()
        ):
            # Try fallback
            lad.warning(
                "llm.stream.fallback",
                extra={
                    "from": primary_model,
                    "to": fallback_model,
                    "reason": msg[:160],
                },
            )
            try:
                yield from stream_model(fallback_model)
                return
            except Exception as e2:
                lad.error("llm.stream.fallback_failed", extra={"error": str(e2)[:200]})
                yield f"[warn] Fallback failed: {e2}"
                return
        else:
            lad.error("llm.stream.error", extra={"error": msg[:200]})
            yield f"[warn] {msg}"
            return


# Orchestrates retrieve → prompt → LLM call. Returns {"answer", "citations", ...meta}.
# On LLM failure, returns a warning + a deterministic summary so UX doesn’t dead-end.
def ask(question: str, scope: dict, *, cid: str | None = None) -> dict:
    """
    Retrieve → build prompt → call LLM (non-stream) → return full answer + citations.
    """
    lad = _log_adapter(cid)
    t0 = time.perf_counter()
    lad.info(
        "retrieval.start",
        extra={**scope, "k": settings.RAG_TOP_K, "q_len": len(question)},
    )
    cards = retrieve(question, scope, k=settings.RAG_TOP_K)
    lad.info(
        "retrieval.done",
        extra={
            "retrieved": len(cards),
            "dur_ms": int((time.perf_counter() - t0) * 1000),
        },
    )
    meta = {
        "retrieved": len(cards),
        **scope,
        "model": settings.GEN_MODEL,
        "provider": settings.LLM_PROVIDER,
    }

    if not cards:
        lad.warning("retrieval.empty", extra={**scope, "q": question[:80]})
        # Diagnostic probe: try without scope to detect scope mismatch vs empty index.
        try:
            t_probe = time.perf_counter()
            probe_cards = retrieve(question, {}, k=3)
            lad.info(
                "retrieval.probe",
                extra={
                    "retrieved": len(probe_cards),
                    "dur_ms": int((time.perf_counter() - t_probe) * 1000),
                },
            )
        except Exception as e:
            probe_cards = []
            lad.error("retrieval.probe.error", extra={"error": str(e)[:200]})

        if probe_cards:
            hint = "Selected scope likely excludes relevant docs. Clear scope or pick a different package/diagram."
        else:
            hint = "Index may be empty or not selected. Verify per-model rag.sqlite and model_id routing."
        return {
            "answer": f"No evidence found for the selected scope.\n\nHint: {hint}",
            "citations": [],
            **meta,
        }

    prompt = _build_prompt(question, cards)
    lad.debug(
        "prompt.built", extra={"chars": len(prompt), "cards_used": min(len(cards), 8)}
    )

    try:
        t1 = time.perf_counter()
        text = _call_llm(prompt, cid=cid)
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
        text = f"[warn] LLM call failed: {e}\n\n" + _simple_summarize(cards)

    return {
        "answer": text,
        "citations": [
            {"doc_id": c.get("doc_id"), "title": c.get("title")} for c in cards[:10]
        ],
        **meta,
    }


# ----------------------------- #
# Public API: ask_stream (yields deltas)
# ----------------------------- #


def ask_stream(
    question: str, scope: dict, *, cid: str | None = None
) -> Generator[str, None, None]:
    """
    Retrieve → build prompt → stream from LLM.
    Yields text deltas (strings). Your FastAPI route can wrap this as:
      - SSE:   yield f"data: {json.dumps({'delta': chunk})}\\n\\n"
      - NDJSON: yield json.dumps({'delta': chunk}) + "\\n"
    """
    lad = _log_adapter(cid)
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
    cards = retrieve(question, scope, k=settings.RAG_TOP_K)
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

    prompt = _build_prompt(question, cards)

    # Stream tokens; if the provider fails, yield a single fallback summary
    yielded_any = False
    try:
        for chunk in _call_llm_stream(prompt, cid=cid):
            yielded_any = True
            if chunk:
                yield chunk
    except Exception as e:
        lad.exception("llm.stream.error")
        # Emit one warning token, then a compact summary
        yield f"[warn] LLM stream failed: {e}\n"
        yield _simple_summarize(cards)
        return

    if not yielded_any:
        lad.warning("llm.stream.empty")
        # Provider returned nothing; give user something useful
        yield _simple_summarize(cards)
