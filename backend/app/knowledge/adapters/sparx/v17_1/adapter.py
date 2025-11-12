# ------------------------------------------------------------
# Module: app/input_adapters/sparx/v17_1/adapter.py
# Purpose: Concrete adapter for Sparx EA v17.1 that provides normalized options for routing.
# ------------------------------------------------------------

"""Sparx EA v17.1 input adapter for consistent routing and configuration.

This adapter defines stable (vendor, version) identifiers and provides
normalized configuration options to integrate with the ingestion pipeline.

Responsibilities
----------------
- Define a unique (vendor, version) pair for Sparx EA v17.1.
- Provide a class-based interface to construct `AdapterOptions`.
- Avoid any direct I/O or database operations (pure configuration layer).
"""

from __future__ import annotations

from app.knowledge.adapters.protocols import AdapterOptions, InputAdapter


# Defines a specific (vendor, version) adapter; values must be stable and lowercase for matching.
# Invariant: this class should not perform I/O or DB creation—only routing/config.
class Sparx171(InputAdapter):
    """Concrete adapter for Sparx EA version 17.1.

    Notes
    -----
    - Identifiers are lowercase and stable for routing consistency.
    - Only responsible for option construction; no I/O or DB access.
    """

    VENDOR = "sparx"
    VERSION = "17.1"

    # Call only after `cls.matches(vendor, version)` is True.
    # Returns adapter-scoped options; user inputs are ignored in favor of class constants.
    @classmethod
    def make_options(cls, vendor: str, version: str) -> AdapterOptions:
        """Return adapter-scoped `AdapterOptions` for Sparx EA v17.1.

        Notes
        -----
        - Should be called only if `cls.matches(vendor, version)` returns True.
        - Delegates to `InputAdapter.make_options`, passing class constants.
        - Currently a safe pass-through (extend here for Sparx-specific settings later).
        """
        return super().make_options(vendor, version)
