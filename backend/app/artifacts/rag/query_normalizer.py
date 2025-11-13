# ------------------------------------------------------------
# Module: app/artifacts/rag/query_normalizer.py
# Purpose: Turn natural-language questions into FTS5 MATCH strings.
# ------------------------------------------------------------


from __future__ import annotations

import re

# --- tiny normalizer to make FTS5 match useful on natural language questions ---
_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "doing",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "why",
    "how",
    "should",
    "would",
    "could",
    "can",
    "we",
    "you",
    "i",
}

_token_re = re.compile(r"[a-z0-9_]+")


def build_match(q: str) -> str:
    """Turn a free-text question into a compact FTS5 MATCH query string.

    Notes
    -----
    - Lowercases, removes stopwords, keeps up to 8 tokens.
    - Adds a trailing `*` for tokens with length ≥ 5 (prefix search).
    - Special-cases the phrase `"missing ports"` when both terms are present.
    - Returns an empty string when nothing useful is extracted (signals fallback).
    """
    toks = [t for t in _token_re.findall(q.lower()) if t not in _STOP]
    if not toks:
        return ""
    stems = []
    for t in toks[:8]:
        stems.append(f"{t}*" if len(t) >= 5 else t)
    phrase = '"missing ports" OR ' if ("missing" in toks and "ports" in toks) else ""
    return f"{phrase}" + " OR ".join(stems)
