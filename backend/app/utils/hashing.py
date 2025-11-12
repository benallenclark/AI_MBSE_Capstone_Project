# ------------------------------------------------------------
# Module: app/utils/hashing.py
# Purpose: Provide SHA-256 hashing utilities for bytes and stream data.
# ------------------------------------------------------------

"""Lightweight helpers for computing SHA-256 checksums.

This module supports both in-memory and streamed hashing, enabling efficient
content-addressable identification of data payloads.

Responsibilities
----------------
- Compute SHA-256 digests for in-memory byte sequences.
- Compute SHA-256 digests for large file streams efficiently.
- Avoid excessive memory use during hash computation.
- Provide consistent hex digest output for integrity verification.
"""

from __future__ import annotations

import hashlib
from typing import BinaryIO


# Compute SHA-256 for an in-memory bytes payload.
def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 of a bytes payload (content-addressable key)."""
    return hashlib.sha256(data).hexdigest()


# Compute SHA-256 for a file-like stream without full memory loading.
def compute_sha256_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute SHA-256 of a file-like object without loading it all in memory.
    Useful for large uploads. Caller should open in binary mode.
    """
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(chunk_size), b""):
        h.update(chunk)
    return h.hexdigest()


__all__ = ["compute_sha256", "compute_sha256_stream"]
