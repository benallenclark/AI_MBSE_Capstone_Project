# ------------------------------------------------------------
# Module: app/input_adapters/router.py
# Purpose: Map (vendor, version) to an InputAdapter class.
# ------------------------------------------------------------

"""Adapter router that resolves `(vendor, version)` pairs to InputAdapter classes.

Responsibilities
----------------
- Maintain a registry of known adapter classes (not instances).
- Perform normalized, ordered matching of `(vendor, version)` inputs.
- Return adapter classes for later instantiation or configuration.
- Raise a clear error when no registered adapter matches.
"""

from __future__ import annotations

from app.input_adapters.protocols import InputAdapter
from app.input_adapters.sparx.v17_1.adapter import Sparx171

# Registry of available adapter CLASSES (not instances).
# Keep entries unique and ordered — the first match wins if overlaps exist.
# Invariant: all adapters must define lowercase VENDOR/VERSION constants.
_REGISTRY: list[type[InputAdapter]] = [Sparx171]


def get_adapter(vendor: str, version: str) -> type[InputAdapter]:
    """Return the adapter class matching `(vendor, version)`.

    Notes
    -----
    - Inputs are normalized to lowercase before matching.
    - Returns the adapter CLASS (call `.make_options()` or instantiate later).
    - Raises `ValueError` if no match is found.
    - For multiple potential matches, the first registered adapter wins.
    """
    v, r = vendor.lower(), version.lower()

    for cls in _REGISTRY:
        if cls.matches(v, r):
            return cls

    # Clear, explicit failure when no adapter matches.
    raise ValueError(f"No adapter for vendor={vendor} version={version}")
