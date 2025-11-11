# ------------------------------------------------------------
# Module: app/criteria/protocols.py
# Purpose: Minimal adapter interface and options for routing by (vendor, version).
# ------------------------------------------------------------

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Mapping

# `frozen=True` prevents reassigning fields but does not deep-freeze nested objects.
# Invariant: treat `AdapterOptions` as read-only; 
# if you need deep immutability, wrap mappings (e.g., MappingProxyType).
@dataclass(frozen=True)
class AdapterOptions:
    vendor: str
    version: str
    
    # room for vendor quirks later (namespaces, known stereotypes, etc.)
    # `frozenset()` is not a Mapping and will fail on `.get`/indexing; use an empty dict or MappingProxyType instead.
    # Invariant: `extra` should behave like a read-only dict of string→string vendor quirks.
    extra: Mapping[str, str] = frozenset()  # cheap immutable mapping

class InputAdapter:
    # Subclasses must set `VENDOR`/`VERSION` to lowercase constants (e.g., "sparx", "17.1").
    # Invariant: these define the adapter’s identity; never derive them from user input.
    VENDOR: str
    VERSION: str

    # Compares `vendor.lower()`/`version.lower()` to class constants; ensure class values are lowercased.
    # Consider trimming whitespace on inputs upstream; unmatched values mean “not my adapter.”
    @classmethod
    def matches(cls, vendor: str, version: str) -> bool:
        return vendor.lower() == cls.VENDOR and version.lower() == cls.VERSION

    # Ignores caller’s strings and emits class constants—call only after `matches(...)` returns True.
    # Invariant: `AdapterOptions.vendor/version` reflect the adapter, not user input; `extra` starts empty.
    @classmethod
    def make_options(cls, vendor: str, version: str) -> AdapterOptions:
        return AdapterOptions(vendor=cls.VENDOR, version=cls.VERSION, extra={})
