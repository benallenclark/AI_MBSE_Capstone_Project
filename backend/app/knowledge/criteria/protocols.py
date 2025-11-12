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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


# Immutable analysis metadata passed to every predicate.
# - Carries vendor/version + per-model paths needed for queries/writes.
# - Designed for pure predicates: treat as read-only.
@dataclass(frozen=True)
class Context:
    """Immutable metadata passed to every predicate evaluation.

    Attributes:
        vendor (str): Model vendor name (e.g., "sparx", "cameo").
        version (str): Vendor tool version string.
        model_id (str | None): Optional unique model identifier for traceability.
        model_dir (Path): Per-model working directory (e.g., for DuckDB, evidence).
        output_root (Path | None): Root for any generated artifacts when needed.

    Example:
        >>> ctx = Context(vendor="sparx", version="17.1", model_id="demo123")
    """

    vendor: str
    version: str
    model_dir: Path
    model_id: str | None = None
    output_root: Path | None = None


# Minimal DB surface to support sqlite3 and duckdb in tests and prod.
# - Keep usage to .execute(...) and read-only SELECTs inside predicates.
class DbLike(Protocol):
    def execute(self, sql: str, params: Iterable[Any] | None = None, /) -> Any: ...


# Predicate contract:
# - Pure function: (db, ctx) -> (passed, details)
# - No I/O, no logging; return small, JSON-serializable 'details'.
# - Deterministic given the same db and ctx.
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

    def __call__(self, db: DbLike, ctx: Context) -> tuple[bool, Mapping[str, Any]]: ...


# Explicit export surface; keep aligned with imports elsewhere.
__all__ = ["Context", "Predicate", "DbLike"]
