# ------------------------------------------------------------
# Module: app/input_adapters/router.py
# Purpose: Register and resolve vendor-specific model adapters for input parsing.
# ------------------------------------------------------------

"""Adapter registry and factory router for model input parsing.

Summary:
    Provides a centralized lookup mechanism to resolve which adapter
    implementation should handle a given (vendor, version) pair.

Details:
    - Each adapter encapsulates how a vendor’s native model format
      (e.g., Sparx `.xml`, Cameo `.mdxml`) is read and transformed
      into the project’s internal representation (e.g., SQLite or Graph-IR).
    - This router acts as a plug-in registry: each (vendor, version)
      maps to a lightweight factory function that returns an adapter instance.
    - The function `get_adapter()` is used by the `/v1/analyze` API route
      to select the correct parser at runtime.

Developer Guidance:
    - To add a new adapter:
        1. Implement the `Adapter` interface in a new module
           (see `app/input_adapters/protocols.py` for details).
        2. Register it in `_ADAPTERS` with a lowercase vendor key
           and matching version string.
    - Keep `_ADAPTERS` explicit and lightweight; avoid dynamic imports or I/O.
    - Always lowercase vendor names for consistency.
    - Unit test adapter registration and error cases to prevent silent misrouting.
"""

from typing import Callable, Dict, Tuple
from .protocols import Adapter
from .sparx.v17_1.adapter import Sparx171

# -----------------------------------------------------------------------------
# Type alias for factory functions
# -----------------------------------------------------------------------------
AdapterFactory = Callable[[], Adapter]

# -----------------------------------------------------------------------------
# Adapter registry
# -----------------------------------------------------------------------------
# Maps (vendor, version) -> callable that returns an adapter instance.
# Example key: ("sparx", "17.1") → Sparx Enterprise Architect v17.1 adapter.
_ADAPTERS: Dict[Tuple[str, str], AdapterFactory] = {
    ("sparx", "17.1"): lambda: Sparx171(),
}


def get_adapter(vendor: str, version: str) -> Adapter:
    """Return the adapter matching a given (vendor, version) pair.

    Args:
        vendor (str): Vendor identifier (case-insensitive), e.g. `"sparx"`, `"cameo"`.
        version (str): Version string for the vendor, e.g. `"17.1"`.

    Returns:
        Adapter: Instantiated adapter ready to parse model input.

    Raises:
        ValueError: If the (vendor, version) combination is not registered.

    Example:
        >>> adapter = get_adapter("sparx", "17.1")
        >>> db = adapter.build_db(xml_bytes)
    """
    key = (vendor.lower(), version)
    try:
        return _ADAPTERS[key]()  # create and return adapter instance
    except KeyError as e:
        raise ValueError(f"Unsupported adapter: {key}") from e