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


# Protocol describing the required interface for any LLM client implementation.
class LLMClient(Protocol):
    # Return the full generated completion for the given prompt.
    def generate(self, prompt: str) -> str: ...

    # Yield generated chunks incrementally for the given prompt.
    def stream(self, prompt: str) -> Iterable[str]: ...
