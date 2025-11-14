# ------------------------------------------------------------
# Module: app/artifacts/intelligence/client/ollama_client.py
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

from app.infra.core.config import settings

from .ollama_http import generate as http_generate
from .ollama_http import stream as http_stream
from .ollama_options import sanitize_options


class OllamaClient:
    """LLM client for Ollama: small public surface, logic delegated to helpers."""

    # Purpose: Initialize the Ollama client with base URL, model names, options, and logger.
    def __init__(
        self,
        model: str,
        host: str,
        options: dict | None = None,
        lad: logging.LoggerAdapter | None = None,
    ):
        self.model = model
        self.host = host  # "ollama" (CLI) or "http://host:11434"
        self.options = sanitize_options(options or {}, lad)
        self.lad = lad or logging.getLogger(__name__)

    @classmethod
    def from_settings(cls, s=settings, lad=None):
        # Single source of truth: Settings → sanitize → client
        return cls(
            model=s.GEN_MODEL,
            host=s.OLLAMA,
            options=s.ollama_options,  # sanitized in __init__
            lad=lad,
        )

    def generate(self, prompt: str, *, opts_override: dict | None = None) -> str:
        # Per-call overrides (rare) → sanitize and merge over base
        opts = dict(self.options)
        if opts_override:
            opts.update(opts_override)
            opts = sanitize_options(opts, self.lad)
        return http_generate(self.host, self.model, prompt, opts)

    def stream(self, prompt: str, *, opts_override: dict | None = None):
        opts = dict(self.options)
        if opts_override:
            opts.update(opts_override)
            opts = sanitize_options(opts, self.lad)
        return http_stream(self.host, self.model, prompt, opts)
