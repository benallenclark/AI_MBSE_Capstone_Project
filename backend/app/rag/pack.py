# ------------------------------------------------------------
# Module: app/rag/pack.py
# Purpose: Pack N evidence cards into a tight, citeable context string.
# ------------------------------------------------------------

from __future__ import annotations
from typing import List, Dict, Any
from app.core.config import settings

# Input: list of evidence card dicts; Output: a single newline-separated context string.
# Precondition: each card should include at least 'doc_id' and ideally 'title' and 'body_text'.
def pack_context(cards: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, c in enumerate(cards, start=1):
        
        # If body_text is empty/whitespace, `splitlines()[0]` will raise IndexError.
        # Either ensure non-empty body_text upstream or guard before indexing; `RAG_MAX_CARD_CHARS` should be a sane small int.
        body_first_line = (c.get("body_text") or "").strip().splitlines()[0][:settings.RAG_MAX_CARD_CHARS]
        
        # Uses doc_id when title is missing; final fallback "(untitled)" keeps formatting stable.
        # If you rely on titles for UX, validate upstream to avoid unreadable contexts.
        title = c.get("title") or c.get("doc_id") or "(untitled)"
        
        # Hard index `c['doc_id']` will KeyError if the field is absent—even though title falls back.
        # Invariant: every card MUST include 'doc_id' (string); enforce upstream or switch to a safe getter.
        lines.append(f"[{i}] {title} (doc_id={c['doc_id']})\n{body_first_line}")
        
    # Joins entries with blank lines; very large `cards` can create huge strings—consider capping N upstream.
    # Caller is responsible for rendering/escaping in UIs (this is plain text).
    return "\n\n".join(lines)
