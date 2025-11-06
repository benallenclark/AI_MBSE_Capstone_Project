# ------------------------------------------------------------
# Module: app/input_adapters/router.py
# Purpose: Map (vendor, version) to an InputAdapter class.
# ------------------------------------------------------------

from __future__ import annotations
from typing import Type
from app.input_adapters.protocols import InputAdapter
from app.input_adapters.sparx.v17_1.adapter import Sparx171

# Contains adapter CLASSES (not instances). Keep entries unique and ordered—first match wins if overlaps exist.
# Invariant: listed adapters must define lowercase VENDOR/VERSION to match normalized inputs.
_REGISTRY: list[Type[InputAdapter]] = [Sparx171]

# Returns the adapter CLASS, not an instance—call classmethods (e.g., .make_options) or instantiate later.
# Precondition: inputs identify exactly one adapter in `_REGISTRY`; otherwise a ValueError is raised.
def get_adapter(vendor: str, version: str) -> Type[InputAdapter]:
    
    # Normalizes inputs to lowercase before matching.
    # Trim/validate upstream to avoid whitespace/version-format mismatches.
    v, r = vendor.lower(), version.lower()
    
    # Iterates in registry order; if two adapters could match, the first one is chosen.
    # Keep more specific adapters earlier to avoid accidental shadowing.
    for cls in _REGISTRY:
        if cls.matches(v, r):
            return cls
        
    # Clear failure when no adapter matches—caller should catch and present supported (vendor, version) pairs.
    # Avoid leaking user-provided strings to logs without sanitization in multi-tenant contexts.
    raise ValueError(f"No adapter for vendor={vendor} version={version}")
