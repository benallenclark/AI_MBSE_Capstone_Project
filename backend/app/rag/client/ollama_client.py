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
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable

import requests

from app.core.config import settings as _settings


# Purpose: Normalize model options and ensure valid numeric values for generation parameters.
def _sanitize(opts: dict | None, lad: logging.LoggerAdapter | None) -> dict:
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


# Purpose: Ensure the base URL for Ollama is fully qualified; default to localhost if not.
def _base_url(val: str) -> str:
    return val if val.startswith("http") else "http://localhost:11434"


# Purpose: Detect if an error message indicates an out-of-memory or capacity-related issue.
def _is_oom(msg: str) -> bool:
    m = (msg or "").lower()
    return (
        ("more system memory" in m)
        or ("unable to load full model" in m)
        or ("out of memory" in m)
    )


class OllamaClient:
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

    # Purpose: Factory method to construct an OllamaClient instance using global settings.
    @classmethod
    def from_settings(
        cls, settings=_settings, lad: logging.LoggerAdapter | None = None
    ) -> OllamaClient:
        if settings.LLM_PROVIDER != "ollama":
            raise RuntimeError(f"Unsupported LLM_PROVIDER={settings.LLM_PROVIDER}")
        base = _base_url(str(settings.OLLAMA))
        fallback = getattr(settings, "FALLBACK_MODEL", "phi3:mini")
        opts = _sanitize(getattr(settings, "ollama_options", {}), lad)
        return cls(base, settings.GEN_MODEL, fallback, opts, lad)

    # Purpose: Send a blocking generation request to Ollama and handle fallback if necessary.
    def generate(self, prompt: str) -> str:
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

    # Purpose: Stream token responses from Ollama in real time, with fallback handling on errors.
    def stream(self, prompt: str) -> Iterable[str]:
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
