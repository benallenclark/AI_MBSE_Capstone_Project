# ------------------------------------------------------------
# Module: app/evidence/types.py
# Purpose: Typed contracts for Evidence v2 payloads (summary + per-entity facts).
# ------------------------------------------------------------

"""Type contracts for Evidence v2 payloads.

Responsibilities
----------------
- Define JSON-serializable shapes for predicate outputs and per-entity facts.
- Provide stable keys used by the UI, RAG, and storage layers.
- Document optional fields to keep payloads flexible and forward-compatible.

Notes
-----
- All values must be JSON-serializable (dict/list/str/int/float/bool/None).
- Adding optional fields is backward-compatible; renaming/removing keys is breaking.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# Category taxonomy used by UI/filters (treat as wire-level enum; changing is breaking).
Category = Literal[
    "structure",
    "interface",
    "behavior",
    "requirements",
    "simulation",
    "views",
    "hygiene",
]

# Default interpretation for predicate findings; predicates may override per-fact via `has_issue`.
Severity = Literal["info", "warn", "error"]


class Measure(TypedDict, total=False):
    """Normalized progress/coverage measure.

    Keys
    ----
    ok : int
        Number of items that passed or are in a good state.
    total : int
        Total number of considered items (use the same scope as `ok`).
    """

    ok: int
    total: int


class Ref(TypedDict, total=False):
    """Lightweight pointer back to a source record or object.

    Keys
    ----
    table : str
        Source table or collection name (e.g., "t_object", "t_connector").
    id : str | int
        Primary key or identifier within the table.
    guid : str
        Optional stable GUID if available.
    role : str
        Role tag for this reference (e.g., "block", "port", "src", "dst", "diagram", "state").
    """

    table: str  # e.g., "t_object", "t_connector"
    id: str | int
    guid: str
    role: str  # e.g., "block", "port", "src", "dst", "diagram", "state"


class Quote(TypedDict, total=False):
    """Optional human-readable snippet supporting a finding.

    Notes
    -----
    Keep snippets small and non-sensitive (no PII or export-controlled content).

    Keys
    ----
    source : str
        Origin field or URI (e.g., "t_object.Name", "xml://path").
    locator : str
        GUID, XPath, or other precise locator.
    snippet : str
        Short excerpt.
    start : int | None
        Start offset if applicable.
    end : int | None
        End offset if applicable.
    """

    source: str  # "t_object.Name" | "xml://path"
    locator: str  # GUID or XPath
    snippet: str
    start: int | None
    end: int | None


class Fact(TypedDict, total=False):
    """One real-world entity (block, port, etc.) associated with a predicate.

    Contract
    --------
    The pair (`subject_type`, `subject_id`) should uniquely and stably identify
    the entity within a model.

    Keys
    ----
    subject_type : str
        Entity kind (e.g., "block", "port", "connector").
    subject_id : str | int
        Stable identifier for the entity.
    subject_name : str
        Human-friendly name (may be empty if unknown).
    has_issue : bool
        True if this entity violates the predicate’s rule (default False).
    child_count : int | None
        Optional count of child items (meaning depends on the predicate).
    tags : list[str]
        Free-form tags that help filter or categorize the entity.
    meta : dict[str, Any]
        Extra machine-usable fields specific to this predicate.
    refs : list[Ref]
        Entity-level provenance; takes precedence over summary-level `refs`.
    quotes : list[Quote]
        Optional supporting quotes/snippets (UI/RAG sugar).
    """

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


class PredicateOutput(TypedDict, total=False):
    """Top-level payload produced by a predicate.

    Keys
    ----
    probe_id : str
        Predicate identifier ("mml_N.rule_name"). The `mml` value should match N.
    mml : int
        Maturity level associated with the rule.
    counts : dict[str, Any]
        Summary counts (predicate-defined; keep small for UI performance).
    facts : list[Fact]
        Per-entity findings. Consider capping for huge models to keep UIs responsive.
    source_tables : list[str]
        Tables or sources consulted (e.g., "t_object"); helps others reproduce results.
    category : Category
        High-level category used by UI filters.
    rule : str
        Predicate rule name (e.g., "ports_typed", "acyclic_generalization").
    severity : Severity
        Default severity for this predicate (entities may override via `has_issue`).
    measure : Measure
        Optional normalized measure (e.g., coverage bars in UI).
    refs : list[Ref]
        Summary-level provenance for the whole predicate (entity-level `refs` override).
    """

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
