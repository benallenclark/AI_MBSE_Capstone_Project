# ------------------------------------------------------------
# Module: app/input_adapters/sparx/v17_1/adapter.py
# Purpose: Concrete adapter for Sparx EA v17.1 that provides normalized options for routing.
# ------------------------------------------------------------

from __future__ import annotations
from app.input_adapters.protocols import InputAdapter, AdapterOptions

# Defines a specific (vendor, version) adapter; values must be stable and lowercase for matching.
# Invariant: this class should not perform I/O or DB creation—only routing/config.
class Sparx171(InputAdapter):
    VENDOR = "sparx"
    VERSION = "17.1"

    # Call only after `cls.matches(vendor, version)` is True.
    # Returns adapter-scoped options; user inputs are ignored in favor of class constants.
    @classmethod
    def make_options(cls, vendor: str, version: str) -> AdapterOptions:
        
        # Delegates to InputAdapter.make_options, which emits 
        # `AdapterOptions` using `cls.VENDOR/cls.VERSION` and an empty `extra`.
        # Safe pass-through for now; extend here later to inject Sparx-specific hints.
        return super().make_options(vendor, version)
