# ------------------------------------------------------------
# Module: app/criteria/protocols.py
# Purpose: Minimal adapter interface and options for routing by (vendor, version).
# ------------------------------------------------------------

"""Base adapter protocol and immutable configuration for vendor/version routing.

This module defines a minimal protocol (`InputAdapter`) and its corresponding
configuration object (`AdapterOptions`) to support adapter discovery and routing
by `(vendor, version)`.

Responsibilities
----------------
- Define a stable, frozen data container (`AdapterOptions`) for adapter metadata.
- Provide a class-based adapter interface that can self-identify via constants.
- Ensure safe, read-only behavior for adapter option propagation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterOptions:
    """Immutable adapter configuration describing a vendor/version pair.

    Notes
    -----
    - Treat as read-only; mutation breaks routing guarantees.
    - `extra` is a mapping of vendor-specific quirks or hints (optional).
    - For deep immutability, wrap mappings externally (e.g., `MappingProxyType`).
    """

    vendor: str
    version: str

    extra: Mapping[str, str] = (
        frozenset()
    )  # empty, lightweight immutable mapping placeholder


class InputAdapter:
    """Base adapter interface for vendor/version-specific configuration.

    Notes
    -----
    - Subclasses must define lowercase `VENDOR` and `VERSION` constants.
    - Intended only for configuration routing — no I/O or data manipulation.
    """

    VENDOR: str
    VERSION: str

    @classmethod
    def matches(cls, vendor: str, version: str) -> bool:
        """Return True if `(vendor, version)` matches this adapter’s identity.

        Notes
        -----
        - Case-insensitive comparison.
        - Whitespace should be trimmed upstream.
        """
        return vendor.lower() == cls.VENDOR and version.lower() == cls.VERSION

    @classmethod
    def make_options(cls, vendor: str, version: str) -> AdapterOptions:
        """Return a new `AdapterOptions` instance for this adapter.

        Notes
        -----
        - Should only be called after `matches()` returns True.
        - Ignores user input and always uses class constants for safety.
        - Starts with an empty `extra` mapping (vendor-specific extensions may populate later).
        """
        return AdapterOptions(vendor=cls.VENDOR, version=cls.VERSION, extra={})
