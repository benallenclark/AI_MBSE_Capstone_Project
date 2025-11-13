# ------------------------------------------------------------
# Module: app/core/ollama_client.py
# Purpose: Client for managing Ollama LLM calls with fallback, streaming, and option sanitization
# ------------------------------------------------------------

"""Interface to the Ollama language model service with support for retries, fallbacks, and streaming.

Responsibilities
----------------
- Sanitize and normalize model options from settings.
- Provide a client abstraction for calling the Ollama API.
- Handle both standard and streaming text generation requests.
- Implement graceful fallback logic for memory or missing model errors.
- Log structured diagnostic and performance information.

Notes
-----
- This module does not cache responses.
- Network calls use `requests`; timeouts are conservative (see per-call timeouts below).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import requests

from app.infra.core.config import settings as _settings

from .ollama_http import base_url, is_oom
from .ollama_options import sanitize_options

# def _sanitize(opts: dict | None, lad: logging.LoggerAdapter | None) -> dict:
#     """Normalize/validate Ollama generation options.

#     Ensures numeric fields are usable floats/ints, applies defaults, and bounds
#     the context window.

#     Notes
#     -----
#     - Defaults: temperature=0.2, top_p=0.95, num_ctx falls back to 2048.
#     - `num_ctx` is capped at 4096; values over that are reset to 2048.
#     - Logs a compact summary at DEBUG level when a logger adapter is provided.
#     """
#     opts = dict(opts or {})

#     def _as_float(k, default):
#         v = opts.get(k)
#         if isinstance(v, str):
#             try:
#                 v = float(v)
#             except ValueError:
#                 v = default
#         if v is None:
#             v = default
#         opts[k] = v

#     _as_float("temperature", 0.2)
#     _as_float("top_p", 0.95)
#     default_ctx = 2048
#     try:
#         num_ctx = int(opts.get("num_ctx", default_ctx))
#     except Exception:
#         num_ctx = default_ctx
#     opts["num_ctx"] = num_ctx if num_ctx <= 4096 else 2048
#     if lad:
#         lad.debug(
#             "ollama.options",
#             extra={
#                 "num_ctx": opts["num_ctx"],
#                 "has_temp": "temperature" in opts,
#                 "has_top_p": "top_p" in opts,
#             },
#         )
#     return opts


# def _base_url(val: str) -> str:
#     """Return a fully-qualified Ollama base URL.

#     Notes
#     -----
#     - If `val` is not an HTTP(S) URL, default to `http://localhost:11434`.
#     """
#     return val if val.startswith("http") else "http://localhost:11434"


# def _is_oom(msg: str) -> bool:
#     """Heuristically detect out-of-memory/capacity errors from a message string."""
#     m = (msg or "").lower()
#     return (
#         ("more system memory" in m)
#         or ("unable to load full model" in m)
#         or ("out of memory" in m)
#     )


class OllamaClient:
    """LLM client for Ollama: small public surface, logic delegated to helpers."""

    # Purpose: Initialize the Ollama client with base URL, model names, options, and logger.
    def __init__(
        self,
        base: str,
        model: str,
        fallback: str | None,
        options: dict,
        lad: logging.LoggerAdapter | None,
    ):
        self.base, self.model, self.fallback, self.options, self.lad = (
            base,
            model,
            fallback,
            options,
            lad,
        )

    @classmethod
    def from_settings(
        cls, settings=_settings, lad: logging.LoggerAdapter | None = None
    ) -> OllamaClient:
        """Construct an `OllamaClient` from global settings.

        Notes
        -----
        - Requires `settings.LLM_PROVIDER == "ollama"`.
        - Falls back to `phi3:mini` unless `FALLBACK_MODEL` is provided.
        - Applies `_sanitize` to `settings.ollama_options`.
        """
        if settings.LLM_PROVIDER != "ollama":
            raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")
        base = base_url(str(settings.OLLAMA))
        model = settings.GEN_MODEL
        fallback = getattr(settings, "FALLBACK_MODEL", None) or "phi3:mini"
        options = sanitize_options(getattr(settings, "ollama_options", {}), lad)
        return cls(base, model, fallback, options, lad)

    def generate(self, prompt: str) -> str:
        """One-shot text generation; tries fallback model on OOM/missing."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "options": self.options,
            "stream": False,
        }
        try:
            r = requests.post(f"{self.base}/api/generate", json=payload, timeout=90)
            r.raise_for_status()
            data = r.json()
            txt = (data or {}).get("response", "") or ""
            if not txt:
                raise RuntimeError("Empty response")
            return txt
        except Exception as e:
            if self.lad:
                self.lad.warning("llm.generate.error", extra={"error": str(e)[:200]})
            if self.fallback and is_oom(e):
                # retry once on fallback
                f_payload = {
                    "model": self.fallback,
                    "prompt": prompt,
                    "options": self.options,
                    "stream": False,  # ← keep non-streaming on fallback too
                }
                fr = requests.post(
                    f"{self.base}/api/generate", json=f_payload, timeout=30
                )
                fr.raise_for_status()
                return (fr.json() or {}).get("response", "") or ""
            raise

    def stream(self, prompt: str) -> Iterable[str]:
        """Streaming text generation; yields text chunks; tries fallback on OOM."""

        def _stream(model: str):
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": self.options,
            }
            with requests.post(
                f"{self.base}/api/generate",
                json=payload,
                stream=True,
                timeout=(5, None),
            ) as r:
                if self.lad:
                    self.lad.info(
                        "llm.stream.open",
                        extra={"model": model, "ok": r.ok, "status": r.status_code},
                    )
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    yield line  # caller assembles the text

        try:
            yield from _stream(self.model)
        except Exception as e:
            if self.fallback and is_oom(e):
                if self.lad:
                    self.lad.info(
                        "llm.stream.oom_retry", extra={"fallback": self.fallback}
                    )
                try:
                    yield from _stream(self.fallback)
                    return
                except Exception as e2:
                    if self.lad:
                        self.lad.error(
                            "llm.stream.fallback_failed", extra={"error": str(e2)[:200]}
                        )
                    yield f"[warn] Fallback failed: {e2}"
                    return
            else:
                if self.lad:
                    self.lad.error("llm.stream.error", extra={"error": str(e)[:200]})
                yield f"[warn] {e}"
