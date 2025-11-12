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

import json
import logging
import time
from collections.abc import Iterable

import requests

from app.core.config import settings as _settings


def _sanitize(opts: dict | None, lad: logging.LoggerAdapter | None) -> dict:
    """Normalize/validate Ollama generation options.

    Ensures numeric fields are usable floats/ints, applies defaults, and bounds
    the context window.

    Notes
    -----
    - Defaults: temperature=0.2, top_p=0.95, num_ctx falls back to 2048.
    - `num_ctx` is capped at 4096; values over that are reset to 2048.
    - Logs a compact summary at DEBUG level when a logger adapter is provided.
    """
    opts = dict(opts or {})

    def _as_float(k, default):
        v = opts.get(k)
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                v = default
        if v is None:
            v = default
        opts[k] = v

    _as_float("temperature", 0.2)
    _as_float("top_p", 0.95)
    default_ctx = 2048
    try:
        num_ctx = int(opts.get("num_ctx", default_ctx))
    except Exception:
        num_ctx = default_ctx
    opts["num_ctx"] = num_ctx if num_ctx <= 4096 else 2048
    if lad:
        lad.debug(
            "ollama.options",
            extra={
                "num_ctx": opts["num_ctx"],
                "has_temp": "temperature" in opts,
                "has_top_p": "top_p" in opts,
            },
        )
    return opts


def _base_url(val: str) -> str:
    """Return a fully-qualified Ollama base URL.

    Notes
    -----
    - If `val` is not an HTTP(S) URL, default to `http://localhost:11434`.
    """
    return val if val.startswith("http") else "http://localhost:11434"


def _is_oom(msg: str) -> bool:
    """Heuristically detect out-of-memory/capacity errors from a message string."""
    m = (msg or "").lower()
    return (
        ("more system memory" in m)
        or ("unable to load full model" in m)
        or ("out of memory" in m)
    )


class OllamaClient:
    """Thin client for the Ollama API with optional fallback model support.

    Parameters
    ----------
    base
        Base URL for the Ollama server (e.g., "http://localhost:11434").
    model
        Primary model name to call.
    fallback
        Optional fallback model name to try on OOM/missing-model errors.
    options
        Generation options passed through to Ollama (already sanitized).
    lad
        Optional `logging.LoggerAdapter` for structured logs.

    Notes
    -----
    - This class is stateless across calls (safe to reuse).
    - All network errors bubble as `RuntimeError` from `generate` or as
      warning strings yielded by `stream` (prefixed with `[warn]`).
    """

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
        base = _base_url(str(settings.OLLAMA))
        fallback = getattr(settings, "FALLBACK_MODEL", "phi3:mini")
        opts = _sanitize(getattr(settings, "ollama_options", {}), lad)
        return cls(base, settings.GEN_MODEL, fallback, opts, lad)

    def generate(self, prompt: str) -> str:
        """Make a blocking text generation call, with optional fallback.

        Behavior
        --------
        - Calls `/api/generate` with `stream=false`.
        - On non-200 responses: if the error looks like OOM/capacity and a
          fallback model is configured, tries the fallback once.
        - Returns the stripped response text on success.
        - Raises `RuntimeError` with a readable message on failure.

        Notes
        -----
        - Request timeout is 90 seconds.
        - Logs open/close timing and status via `lad` if provided.
        """

        def _call(model: str) -> tuple[bool, str]:
            t0 = time.perf_counter()
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": self.options,
            }
            if self.lad:
                self.lad.info("llm.call", extra={"model": model})
            r = requests.post(f"{self.base}/api/generate", json=payload, timeout=90)
            if self.lad:
                self.lad.info(
                    "llm.call.done",
                    extra={
                        "model": model,
                        "ok": r.ok,
                        "status": r.status_code,
                        "dur_ms": int((time.perf_counter() - t0) * 1000),
                    },
                )
            if not r.ok:
                return False, f"Ollama {r.status_code}: {r.text}"
            return True, (r.json().get("response") or "").strip()

        ok, resp = _call(self.model)
        if ok:
            return resp
        if self.fallback and _is_oom(resp):
            if self.lad:
                self.lad.warning(
                    "llm.fallback",
                    extra={"reason": "oom", "from": self.model, "to": self.fallback},
                )
            ok2, resp2 = _call(self.fallback)
            if ok2:
                return resp2
            raise RuntimeError(f"[fallback failed] {resp2}")
        raise RuntimeError(resp)

    def stream(self, prompt: str) -> Iterable[str]:
        """Stream tokens from Ollama in real time, with one-shot fallback.

        Behavior
        --------
        - Opens a streaming connection (`stream=true`) and yields response chunks.
        - On open failure: if the error suggests OOM or missing model and a
          fallback is configured, attempts the fallback stream once.
        - On fallback failure: yields a single warning line and returns.
        - On other errors: yields a single warning line and returns.

        Notes
        -----
        - Timeout is `(connect=5s, read=None)` for streaming.
        - Yields only text chunks and final warnings; caller assembles output.
        - Emits structured logs for open, first token, and done events when
          a logger adapter is provided.
        """

        def _stream(model: str):
            t0 = time.perf_counter()
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
                if not r.ok:
                    if self.lad:
                        self.lad.info(
                            "llm.stream.open",
                            extra={
                                "model": model,
                                "ok": False,
                                "status": r.status_code,
                                "dur_ms": int((time.perf_counter() - t0) * 1000),
                            },
                        )
                    raise RuntimeError(f"Ollama {r.status_code}: {r.text}")
                if self.lad:
                    self.lad.info(
                        "llm.stream.open",
                        extra={
                            "model": model,
                            "ok": True,
                            "status": r.status_code,
                            "dur_ms": int((time.perf_counter() - t0) * 1000),
                        },
                    )
                first = True
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = obj.get("response")
                    if chunk:
                        if first and self.lad:
                            self.lad.info(
                                "llm.stream.first_token", extra={"model": model}
                            )
                        first = False
                        yield chunk
                    if obj.get("done"):
                        if self.lad:
                            self.lad.info("llm.stream.done", extra={"model": model})
                        break

        try:
            yield from _stream(self.model)
        except Exception as e:
            msg = str(e).lower()
            if self.fallback and (
                _is_oom(msg) or "model not found" in msg or "no such file" in msg
            ):
                if self.lad:
                    self.lad.warning(
                        "llm.stream.fallback",
                        extra={
                            "from": self.model,
                            "to": self.fallback,
                            "reason": str(e)[:160],
                        },
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
