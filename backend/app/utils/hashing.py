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

Notes
-----
- Always returns lowercase hexadecimal digests.
- Stream hashing reads in fixed-size chunks (default: 1 MB).
"""

from __future__ import annotations

import hashlib
from typing import BinaryIO


def compute_sha256(data: bytes) -> str:
    """Return the SHA-256 hex digest of an in-memory bytes payload.

    Notes
    -----
    - Designed for small/medium payloads that comfortably fit in memory.
    - Use `compute_sha256_stream` for larger files or uploads.
    """
    return hashlib.sha256(data).hexdigest()


def compute_sha256_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 digest for a binary stream efficiently.

    Parameters
    ----------
    stream : BinaryIO
        File-like object opened in binary mode.
    chunk_size : int, optional
        Number of bytes to read per iteration. Defaults to 1 MB.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.

    Notes
    -----
    - Does not close the stream (caller retains responsibility).
    - Safe for arbitrarily large files; memory use is bounded by `chunk_size`.
    """
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(chunk_size), b""):
        h.update(chunk)
    return h.hexdigest()


__all__ = ["compute_sha256", "compute_sha256_stream"]
