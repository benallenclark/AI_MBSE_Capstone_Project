# ------------------------------------------------------------
# Module: types.py
# Purpose: TypedDict schemas for ask/answer results and citations
# ------------------------------------------------------------

"""Structured typing for ask/answer responses and their citations.

Responsibilities
----------------
- Define the ``Citation`` schema (``doc_id``, ``title``).
- Define the ``AskResult`` schema with ``answer``, ``citations``, and passthrough metadata.
- Allow optional, dynamic scope keys using ``NotRequired`` for flexibility.
- Improve static type checking and IDE assistance without runtime overhead.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class Citation(TypedDict):
    doc_id: str | None
    title: str | None


class AskResult(TypedDict):
    answer: str
    citations: list[Citation]
    # passthrough meta
    retrieved: int
    model: str
    provider: str
    # scope keys are dynamic; keep NotRequired for flexibility
    package: NotRequired[str]
    diagram: NotRequired[str]
