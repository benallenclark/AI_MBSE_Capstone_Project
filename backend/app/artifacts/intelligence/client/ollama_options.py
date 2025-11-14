# ------------------------------------------------------------
# Module: app/artifacts/rag/client/ollama_options.py
# Purpose: Normalize/sanitize Ollama generation options; enforce sane bounds.
# ------------------------------------------------------------

from __future__ import annotations

import logging


def sanitize_options(
    opts: dict | None, lad: logging.LoggerAdapter | None = None
) -> dict:
    opts = dict(opts or {})

    def _as_float(k: str, default: float):
        v = opts.get(k, default)
        try:
            v = float(v)
        except Exception:
            v = default
        opts[k] = v

    def _as_int(k: str, default: int, lo: int | None = None, hi: int | None = None):
        v = opts.get(k, default)
        try:
            v = int(v)
        except Exception:
            v = default
        if lo is not None and v < lo:
            v = lo
        if hi is not None and v > hi:
            v = hi
        opts[k] = v

    _as_float("temperature", 0.2)
    _as_float("top_p", 0.95)
    _as_float("repeat_penalty", 1.1)

    _as_int("top_k", 40, lo=0, hi=10000)
    _as_int("num_predict", 512, lo=16, hi=8192)

    # keep your original ctx cap logic
    default_ctx = 2048
    try:
        num_ctx = int(opts.get("num_ctx", default_ctx))
    except Exception:
        num_ctx = default_ctx
    opts["num_ctx"] = num_ctx if num_ctx <= 4096 else 2048

    # seed can be None or int
    if "seed" in opts and opts["seed"] is not None:
        try:
            opts["seed"] = int(opts["seed"])
        except Exception:
            opts["seed"] = None

    if lad:
        lad.debug(
            "ollama.options",
            extra={
                "num_ctx": opts["num_ctx"],
                "num_predict": opts.get("num_predict"),
                "top_k": opts.get("top_k"),
                "temperature": opts.get("temperature"),
                "top_p": opts.get("top_p"),
            },
        )
    return opts
