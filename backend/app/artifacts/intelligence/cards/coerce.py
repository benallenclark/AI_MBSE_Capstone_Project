# ------------------------------------------------------------
# Module: app/artifacts/evidence/coerce.py
# Purpose: Coerce predicate payloads (dict/dataclass/POJO) to predictable mappings.
# ------------------------------------------------------------

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def to_mapping(obj: Any) -> dict[str, Any]:
    """Return mapping for predicate-level payloads; accept dict/dataclass/POJO."""
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    # POJO: best-effort attribute copy
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}


def fact_to_mapping(obj: Any) -> dict[str, Any]:
    """Return mapping for fact-level payloads; accept dict/dataclass/POJO."""
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
