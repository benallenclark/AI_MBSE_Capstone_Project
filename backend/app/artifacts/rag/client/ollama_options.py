# ------------------------------------------------------------
# Module: app/artifacts/rag/client/ollama_options.py
# Purpose: Normalize/sanitize Ollama generation options; enforce sane bounds.
# ------------------------------------------------------------

from __future__ import annotations

import logging


def sanitize_options(
    opts: dict | None, lad: logging.LoggerAdapter | None = None
) -> dict:
    """Coerce string/None values to numbers; cap num_ctx; log final options."""
    opts = dict(opts or {})

    def _as_float(k: str, default: float):
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
    # keep original cap logic intact
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
