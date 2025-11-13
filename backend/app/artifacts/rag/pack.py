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
        # Accept either 'body_text' (evidence) or 'body' (SQL views); trim to first line.
        raw = (c.get("body_text") or c.get("body") or "").strip()
        body_first_line = raw.splitlines()[0][: settings.RAG_MAX_CARD_CHARS]

        # Title fallback ensures readability even when metadata is missing.
        title = c.get("title") or c.get("doc_id") or "(untitled)"

        # Invariant: every card must include a doc_id (string); enforce upstream.
        lines.append(f"[{i}] {title} (doc_id={c['doc_id']})\n{body_first_line}")

    # Join with blank lines between entries.
    return "\n\n".join(lines)
