# ------------------------------------------------------------
# Module: types.py
# Purpose: TypedDict schemas for ask/answer results and citations
# ------------------------------------------------------------

"""Structured typing for ask/answer responses and their citations.

Responsibilities
----------------
- Define the `Citation` schema (`doc_id`, `title`).
- Define the `AskResult` schema with `answer`, `citations`, and passthrough metadata.
- Support optional scope keys (e.g., `package`, `diagram`) via `NotRequired` for flexibility.
- Provide static type clarity without introducing runtime cost or constraints.

Notes
-----
These types are purely for typing and IDE support — no runtime validation occurs.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class Citation(TypedDict):
    """Reference to a retrieved document or source card."""

    doc_id: str | None
    title: str | None


class AskResult(TypedDict):
    """Full result from a RAG `ask` call (sync or stream)."""

    answer: str
    citations: list[Citation]
    retrieved: int  # number of cards retrieved before LLM call
    model: str  # LLM model name used for the generation
    provider: str  # LLM provider (e.g., 'ollama', 'openai')

    # Optional scope metadata; used to trace which part of the knowledge base was queried
    package: NotRequired[str]
    diagram: NotRequired[str]
