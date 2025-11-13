# ------------------------------------------------------------
# Module: app/artifacts/rag/client/ollama_http.py
# Purpose: Small HTTP/URL helpers for the Ollama client.
# ------------------------------------------------------------

from __future__ import annotations


def base_url(val: str | None) -> str:
    v = (val or "").strip().rstrip("/")
    if not v:
        return "http://127.0.0.1:11434"
    if v.startswith(("http://", "https://")):
        return v
    if ":" in v:  # e.g., 127.0.0.1:11434
        return f"http://{v}"
    return "http://127.0.0.1:11434"


def is_oom(err: Exception) -> bool:
    """Predicate: classify exceptions that mean 'try fallback model'."""
    s = str(err).lower()
    for token in ("out of memory", "oom", "not enough vram", "no such model"):
        if token in s:
            return True
    return False
