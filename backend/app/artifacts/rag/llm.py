# ------------------------------------------------------------
# Module: app/artifacts/rag/llm.py
# Purpose: LLM adapters (Ollama now; others can be added later)
# ------------------------------------------------------------

"""Adapters for querying LLMs, currently supporting Ollama via HTTP or local CLI.

This module defines a minimal `ask_ollama()` helper that can send prompts either
to a running Ollama server (over HTTP/S) or to a local executable, depending on
the configured endpoint. Other backends can be added later with the same pattern.

Responsibilities
----------------
- Send a text prompt to an Ollama-compatible endpoint or binary.
- Return the model’s plain-text response.
- Leave all network and process errors to be handled by the caller.

Notes
-----
- Sensitive prompts may leave the host when using HTTP endpoints.
- 300 s timeout applies only to HTTP; the local CLI path has no timeout.
- Callers should handle `HTTPError`, `URLError`, and `OSError` explicitly.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request

from app.infra.core.config import settings


def ask_ollama(prompt: str, model: str | None = None) -> str:
    """Send a prompt to an Ollama model (HTTP or local CLI) and return the response text.

    Parameters
    ----------
    prompt : str
        The text prompt to send (may contain sensitive data).
    model : str | None, optional
        Model name to use; defaults to `settings.GEN_MODEL`.

    Returns
    -------
    str
        The model’s response text.

    Notes
    -----
    - Chooses HTTP if `settings.OLLAMA` starts with http/https; otherwise treats it as a CLI path.
    - For HTTP, sends JSON `{"model", "prompt", "stream": False}` to `/api/generate`.
    - Returns an empty string if the response JSON lacks a `response` key.
    - For CLI mode, runs `[OLLAMA_PATH, "run", model]` and returns stdout as UTF-8 text.
    - Errors (HTTPError, URLError, OSError) are not caught here—callers must handle them.
    """
    # Fall back to configured default; will fail later if model isn't available at the endpoint/CLI.
    model = model or settings.GEN_MODEL
    endpoint = settings.OLLAMA

    # HTTP(S) mode — prompt leaves host; use HTTPS for production/sensitive data.
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/api/generate",
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 300 s hard timeout; caller should handle timeouts and errors.
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8", "ignore")).get("response", "")

    # Local CLI mode — no timeout; process can hang indefinitely.
    out = subprocess.run(
        [endpoint, "run", model], input=prompt.encode("utf-8"), capture_output=True
    )

    # Decode output, ignoring undecodable bytes for robustness.
    return out.stdout.decode("utf-8", errors="ignore")
