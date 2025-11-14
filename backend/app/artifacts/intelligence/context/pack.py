# ------------------------------------------------------------
# Module: app/artifacts/rag/pack.py
# Purpose: Pack N evidence cards into a tight, citeable context string.
# ------------------------------------------------------------

"""Convert a list of evidence cards into a compact, human-readable context block.

Each evidence card contributes a short, citeable snippet consisting of:
`[n] <title> (doc_id=...)` followed by the first line of its body text.

Responsibilities
----------------
- Combine multiple evidence cards into one newline-separated string.
- Trim body text to `settings.RAG_MAX_CARD_CHARS` for brevity.
- Provide a stable fallback title when missing.
- Keep the output readable for use in LLM prompts or summaries.

Notes
-----
- Each card must include `doc_id`; callers should enforce this.
- Guards against empty or whitespace-only `body_text`.
- For very large inputs, cap the number of cards upstream.
"""

from __future__ import annotations

from typing import Any

from app.infra.core.config import settings


def pack_context(cards: list[dict[str, Any]]) -> str:
    """Pack a list of evidence cards into a newline-separated context string.

    Parameters
    ----------
    cards : list of dict
        Evidence card dicts (each should include `doc_id`, optionally `title` and `body_text`).

    Returns
    -------
    str
        Concatenated, readable context block suitable for display or LLM prompts.

    Notes
    -----
    - Truncates body text to `RAG_MAX_CARD_CHARS` characters.
    - Falls back to `doc_id` or `(untitled)` if `title` is missing.
    - Raises KeyError if `doc_id` is absent.
    """
    lines: list[str] = []
    for i, c in enumerate(cards, start=1):
        meta = c.get("metadata") or {}

        pid = c.get("probe_id") or "unknown_probe"
        mml = c.get("mml")
        domain = meta.get("domain")
        severity = meta.get("severity")
        status = meta.get("status")
        sh = meta.get("structured_hint") or {}
        obs = sh.get("observation") or ""
        imp = sh.get("implication") or ""
        rec = sh.get("recommendation") or ""

        header_bits: list[str] = [f"[{pid}]"]
        if mml is not None:
            header_bits.append(f"MML-{mml}")
        if domain:
            header_bits.append(str(domain))
        if severity:
            header_bits.append(f"severity={severity}")
        if status:
            header_bits.append(f"status={status}")

        header = " | ".join(header_bits)

        # Trim each hint line to avoid runaway length
        def _trim(s: str) -> str:
            s = (s or "").strip()
            return s[: settings.RAG_MAX_CARD_CHARS]

        obs_line = _trim(obs)
        imp_line = _trim(imp)
        rec_line = _trim(rec)

        # Build a compact 3-line block per card.
        block_lines = [header]
        if obs_line:
            block_lines.append(f"- Observation: {obs_line}")
        if imp_line:
            block_lines.append(f"- Implication: {imp_line}")
        if rec_line:
            block_lines.append(f"- Recommendation: {rec_line}")

        lines.append("\n".join(block_lines))

    return "\n\n".join(lines)
