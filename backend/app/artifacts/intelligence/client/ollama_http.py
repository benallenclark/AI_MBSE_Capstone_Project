# ------------------------------------------------------------
# Module: app/artifacts/rag/client/ollama_http.py
# Purpose: Small HTTP/URL helpers for the Ollama client.
# ------------------------------------------------------------

from __future__ import annotations

import json

import requests

DEFAULT_HTTP_TIMEOUT = 180  # give Ollama enough time to pull/warm


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


def generate(host: str, model: str, prompt: str, options: dict) -> str:
    """Call Ollama /api/generate once and return the full response text."""
    url = f"{base_url(host)}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options or {},
    }
    r = requests.post(url, json=payload, timeout=DEFAULT_HTTP_TIMEOUT)
    r.raise_for_status()
    # Ollama returns JSON like {"response": "...", "done": true, ...}
    if "application/json" in (r.headers.get("content-type") or "").lower():
        data = r.json()
    else:
        data = json.loads(r.text)
    return data.get("response", "")


def stream(host: str, model: str, prompt: str, options: dict):
    """Yield text chunks from Ollama /api/generate with stream=True."""
    url = f"{base_url(host)}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": options or {},
    }
    with requests.post(
        url, json=payload, stream=True, timeout=DEFAULT_HTTP_TIMEOUT
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            chunk = obj.get("response")
            if chunk:
                yield chunk
            if obj.get("done"):
                break
