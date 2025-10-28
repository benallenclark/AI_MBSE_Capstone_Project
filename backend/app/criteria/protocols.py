# ------------------------------------------------------------
# Module: app/criteria/protocols.py
# Purpose: Define core predicate interfaces and shared context types.
# ------------------------------------------------------------

"""Core predicate protocols and context definitions.

Summary:
    Defines the shared data structures and callable interface used by all
    maturity predicates. This ensures consistent type hints, signatures,
    and interoperability across the maturity evaluation system.

Details:
    - `Context` carries immutable metadata describing the current analysis.
    - `DbLike` aliases `sqlite3.Connection` for readability and flexibility.
    - `Predicate` defines the required callable signature for all predicates.
      Each predicate must accept a live database and context, then return
      a `(passed: bool, details: dict)` tuple.

Developer Guidance:
    - Use `Context` to access metadata like vendor, version, and model_id.
    - Keep all predicate functions pure: no I/O, no logging side effects.
    - Return small `details` dicts with structured evidence for front-end rendering.
"""

from dataclasses import dataclass
from typing import Protocol, Any, Tuple, Mapping
import sqlite3


# -----------------------------------------------------------------------------
# Analysis context
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Context:
    """Immutable metadata passed to every predicate evaluation.

    Attributes:
        vendor (str): Model vendor name (e.g., "sparx", "cameo").
        version (str): Vendor tool version string.
        model_id (str | None): Optional unique model identifier for traceability.

    Example:
        >>> ctx = Context(vendor="sparx", version="17.1", model_id="demo123")
    """
    vendor: str
    version: str
    model_id: str | None = None


# -----------------------------------------------------------------------------
# Type aliases
# -----------------------------------------------------------------------------
DbLike = sqlite3.Connection
"""Alias for database handle type. Keeps predicates decoupled from concrete DB drivers."""


# -----------------------------------------------------------------------------
# Predicate interface
# -----------------------------------------------------------------------------
class Predicate(Protocol):
    """Callable interface every maturity predicate must implement.

    Signature:
        (db, ctx) -> (passed: bool, details: dict)

    Args:
        db (DbLike): Read-only SQLite connection containing parsed model data.
        ctx (Context): Metadata describing vendor, version, and model ID.

    Returns:
        Tuple[bool, dict[str, Any]]:
            - bool: Whether the predicate passed.
            - dict[str, Any]: Evidence or computed metrics to include in results.

    Example:
        >>> def evaluate(db, ctx):
        ...     rows = db.execute("SELECT COUNT(*) FROM t_object").fetchone()[0]
        ...     return rows > 0, {"object_count": rows}
    """
    def __call__(self, db: DbLike, ctx: Context) -> Tuple[bool, Mapping[str, Any]]:
        ...


__all__ = ["Context", "Predicate", "DbLike"]
