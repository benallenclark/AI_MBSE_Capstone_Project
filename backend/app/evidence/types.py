# ------------------------------------------------------------
# Module: app/evidence/types.py
# Purpose: Typed contracts for Evidence v2 payloads (summary + per-entity facts).
# ------------------------------------------------------------

from __future__ import annotations

# All types here must be JSON-serializable (plain dict/list/str/int/float/bool/None).
# Adding optional fields is backward-compatible; renaming/removing keys is breaking.
from typing import Any, Literal, TypedDict

# Category taxonomy used by UI/filters.
# Treat values as wire-level enums (changing is breaking).
Category = Literal[
    "structure",
    "interface",
    "behavior",
    "requirements",
    "simulation",
    "views",
    "hygiene",
]

# Default interpretation for predicate findings;
# predicates may override per-fact via 'has_issue'.
Severity = Literal["info", "warn", "error"]


# 'total=False' means every field here is optional. Include only what you actually know.
# This keeps payloads flexible for future additions.
class Measure(TypedDict, total=False):
    ok: int
    total: int


# Lightweight pointers back to source rows/objects. 'table'+'id' should be sufficient to re-query;
# 'guid' is included for tools that favor GUIDs. 'role' tags how this ref participates (e.g., src/dst/block/port).
class Ref(TypedDict, total=False):
    table: str  # e.g., "t_object", "t_connector"
    id: str | int
    guid: str
    role: str  # e.g., "block", "port", "src", "dst", "diagram", "state"


# Optional human-readable evidence; keep snippets small and non-sensitive (no PII/export-controlled content).
class Quote(TypedDict, total=False):
    source: str  # "t_object.Name" | "xml://path"
    locator: str  # GUID or XPath
    snippet: str
    start: int | None
    end: int | None


# One Fact = one real thing in the model (block, port, etc.).
# The pair (subject_type, subject_id) should uniquely and stably identify it within a model.
class Fact(TypedDict, total=False):
    subject_type: str
    subject_id: str | int
    subject_name: str
    has_issue: bool
    child_count: int | None
    tags: list[str]
    meta: dict[str, Any]

    # If provided here, these refs take priority over the summary-level 'refs'.
    # Use when this specific entity has its own source evidence.
    refs: list[Ref]

    # Optional supporting quotes/snippets (UI/RAG sugar)
    quotes: list[Quote]


# The UI keys off 'probe_id' ("mml_N.rule_name") and 'mml'.
# Keep them consistent: 'mml' should match the N in 'probe_id' for clear grouping.
class PredicateOutput(TypedDict, total=False):
    probe_id: str  # "mml_2.block_has_port"
    mml: int
    counts: dict[str, Any]  # summary counts

    # May be large; try to cap or summarize for huge models so the UI stays fast.
    facts: list[Fact]

    # Name the tables we queried (e.g., "t_object"); helps others reproduce the result.
    source_tables: list[str]

    # Universal, optional
    category: Category
    rule: str  # "ports_typed", "acyclic_generalization", ...
    severity: Severity  # default severity for this predicate
    measure: Measure  # summary-level measure

    # General provenance for the whole predicate. Entity-level 'refs' will override this when present.
    refs: list[Ref]  # summary-level provenance
