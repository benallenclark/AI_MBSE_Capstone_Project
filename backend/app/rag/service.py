# ------------------------------------------------------------
# Module: app/rag/service.py
# Purpose: Retrieve evidence, build prompts, and 
#          call Ollama (non-stream/stream) with safe defaults and fallback.
# ------------------------------------------------------------

from __future__ import annotations
import json
from typing import Dict, Generator, List, Optional, Tuple
import requests
from app.rag.retrieve import retrieve
from app.core.config import settings



# Normalizes user/config options to JSON-safe types and conservative defaults.
# Guards against bad strings (e.g., "0.2") and unbounded context windows that spike memory.
def _sanitize_ollama_options(opts: Optional[Dict]) -> Dict:
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

    return opts

# Inputs: user question + top evidence cards; Output: a compact, citeable prompt string.
# Keep inputs sanitized—very large `cards` bodies will bloat prompts and slow generation.
def _build_prompt(question: str, cards: List[Dict]) -> str:
    """
    Compose a compact prompt from top evidence cards.
    Keep it small; streaming is about responsiveness.
    """

    # Limit cards to a small N to stay within context; 
    # increase only if you’ve measured quality vs. latency.
    N = 8
    parts: List[str] = []
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


def _simple_summarize(cards: List[Dict]) -> str:
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
    return ("more system memory" in msg) or ("unable to load full model" in msg) or ("out of memory" in msg)


# Returns the full model response or raises RuntimeError on failure.
# Side effects: network call to Ollama; caller should treat output as untrusted text.
def _call_llm(prompt: str) -> str:
    """
    Call the configured LLM and return the full string response.
    Keeps provider branching contained here.
    """
    if settings.LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")

    base = _ollama_base_url()
    primary_model = settings.GEN_MODEL
    fallback_model = getattr(settings, "FALLBACK_MODEL", "phi3:mini")

    def _generate(model_name: str) -> Tuple[bool, str]:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": _sanitize_ollama_options(getattr(settings, "ollama_options", {})),
        }
        
        # 90s total timeout—slow or large generations may exceed this. Tune per deployment.
        # Errors bubble up as RuntimeError (below); include payload options in logs for diagnosis.
        r = requests.post(f"{base}/api/generate", json=payload, timeout=90)
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
        ok2, resp2 = _generate(fallback_model)
        if ok2:
            return resp2
        raise RuntimeError(f"[fallback failed] {resp2}")

    # Other errors: surface payload for observability
    raise RuntimeError(resp)

# Yields text chunks as they arrive; consumers should frame as SSE/NDJSON.
# Converts most failures into a single warning (and may try a tiny fallback model).
def _call_llm_stream(prompt: str) -> Generator[str, None, None]:
    """
    Stream tokens from the configured LLM via Ollama NDJSON.
    Yields text deltas. Caller frames as SSE/NDJSON.
    """
    if settings.LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")

    base = _ollama_base_url()
    primary_model = settings.GEN_MODEL
    fallback_model = getattr(settings, "FALLBACK_MODEL", "qwen2.5:0.5b-instruct-q4_0")  # tiny & reliable

    def stream_model(model_name: str) -> Generator[str, None, None]:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": _sanitize_ollama_options(getattr(settings, "ollama_options", {})),
        }

        # 5s connect timeout, infinite read—hung servers can stall forever. 
        # Add a read timeout if needed.
        # Parses NDJSON per line; non-JSON lines are ignored for resilience.
        with requests.post(f"{base}/api/generate", json=payload, stream=True, timeout=(5, None)) as r:
            if not r.ok:
                # Surface body so caller can decide about fallback
                raise RuntimeError(f"Ollama {r.status_code}: {r.text}")
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = obj.get("response")
                if chunk:
                    yield chunk
                if obj.get("done"):
                    break

    # Try primary
    try:
        yield from stream_model(primary_model)
        return
    except Exception as e:
        msg = str(e)
        if _is_ollama_oom(msg) or "model not found" in msg.lower() or "no such file" in msg.lower():
            # Try fallback
            try:
                yield from stream_model(fallback_model)
                return
            except Exception as e2:
                yield f"[warn] Fallback failed: {e2}"
                return
        else:
            yield f"[warn] {msg}"
            return

# Orchestrates retrieve → prompt → LLM call. Returns {"answer", "citations", ...meta}.
# On LLM failure, returns a warning + a deterministic summary so UX doesn’t dead-end.
def ask(question: str, scope: Dict) -> Dict:
    """
    Retrieve → build prompt → call LLM (non-stream) → return full answer + citations.
    """
    cards = retrieve(question, scope, k=settings.RAG_TOP_K)
    meta = {
        "retrieved": len(cards),
        **scope,
        "model": settings.GEN_MODEL,
        "provider": settings.LLM_PROVIDER,
    }

    if not cards:
        return {
            "answer": "I couldn't find any evidence for that scope. Run step 3 (bootstrap index) and try again.",
            "citations": [],
            **meta,
        }

    prompt = _build_prompt(question, cards)

    try:
        text = _call_llm(prompt)
        if not text.strip():
            raise RuntimeError("Empty response from LLM")
    except Exception as e:
        text = f"[warn] LLM call failed: {e}\n\n" + _simple_summarize(cards)

    return {
        "answer": text,
        "citations": [{"doc_id": c.get("doc_id"), "title": c.get("title")} for c in cards[:10]],
        **meta,
    }


# ----------------------------- #
# Public API: ask_stream (yields deltas)
# ----------------------------- #

def ask_stream(question: str, scope: Dict) -> Generator[str, None, None]:
    """
    Retrieve → build prompt → stream from LLM.
    Yields text deltas (strings). Your FastAPI route can wrap this as:
      - SSE:   yield f"data: {json.dumps({'delta': chunk})}\\n\\n"
      - NDJSON: yield json.dumps({'delta': chunk}) + "\\n"
    """
    cards = retrieve(question, scope, k=settings.RAG_TOP_K)

    if not cards:
        yield "I couldn't find any evidence for that scope. Run step 3 (bootstrap index) and try again."
        return

    prompt = _build_prompt(question, cards)

    # Stream tokens; if the provider fails, yield a single fallback summary
    yielded_any = False
    try:
        for chunk in _call_llm_stream(prompt):
            yielded_any = True
            if chunk:
                yield chunk
    except Exception as e:
        # Emit one warning token, then a compact summary
        yield f"[warn] LLM stream failed: {e}\n"
        yield _simple_summarize(cards)
        return

    if not yielded_any:
        # Provider returned nothing; give user something useful
        yield _simple_summarize(cards)
