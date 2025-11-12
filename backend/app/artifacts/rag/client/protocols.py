# ------------------------------------------------------------
# Module: app/llm/protocols.py
# Purpose: Define a minimal protocol for LLM client interfaces (sync and streaming).
# ------------------------------------------------------------

"""Typed protocol for Large Language Model (LLM) client implementations.

This module declares the expected interface for any LLM client used by the app,
covering both full-response generation and token streaming.

Responsibilities
----------------
- Provide a standard `generate(prompt)` contract for synchronous responses.
- Provide a standard `stream(prompt)` contract for incremental token yields.
- Enable static type-checking and IDE support across interchangeable clients.
- Decouple application code from specific LLM provider SDKs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class LLMClient(Protocol):
    """Protocol defining the minimal contract for any LLM client.

    Implementations should provide both synchronous and streaming methods
    for generating text completions. This enables the app to use any
    compatible client interchangeably without binding to a specific SDK.
    """

    def generate(self, prompt: str) -> str: ...

    """Return the full generated completion for the given prompt.

    Notes
    -----
    - This method should block until the complete text is available.
    - Used for standard, single-shot completions.
    """

    def stream(self, prompt: str) -> Iterable[str]: ...

    """Yield generated text chunks incrementally for the given prompt.

    Notes
    -----
    - Use this for streaming responses token by token or chunk by chunk.
    - Should yield partial strings as they become available.
    """
