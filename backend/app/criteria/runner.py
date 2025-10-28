# ------------------------------------------------------------
# Module: app/criteria/runner.py
# Purpose: Execute all maturity predicates against parsed models.
# ------------------------------------------------------------

"""Predicate runner: executes all maturity tests (predicates) against a parsed model.

Summary:
    Orchestrates discovery and execution of predicate functions across
    maturity-level groups (MML-1…MML-10). Each predicate function receives
    a live database handle and contextual metadata, then returns a boolean
    and an evidence dictionary.

Details:
    - Discovers all predicates dynamically via `criteria.loader.discover()`.
    - Each predicate returns `(passed: bool, details: dict)`.
    - Produces an `EvidenceItem` list summarizing which predicates passed.
    - Aggregates a numeric maturity level = count of passed predicates.

Developer Guidance:
    - Extendable: add new predicates under `app/criteria/mml_*`.
    - Ensure each predicate function is deterministic and idempotent.
    - Avoid long-running queries; all checks must complete quickly.
"""


from typing import List
from .protocols import Context, DbLike
from .loader import discover
from app.api.v1.models import EvidenceItem


def run_predicates(
    db: DbLike,
    ctx: Context,
    groups: list[str] | None = None
) -> tuple[int, List[EvidenceItem]]:
    """Run all discovered maturity predicates and return results.

    Args:
        db: Database-like object (typically an SQLite connection) containing parsed model data.
        ctx: Context object containing metadata such as vendor, version, and model_id.
        groups: Optional list of predicate groups to restrict execution
                (e.g., `["mml_1", "mml_2"]`). If None, all groups are run.

    Returns:
        tuple:
            int: Aggregate maturity level (count of passed predicates).
            List[EvidenceItem]: Structured results for all predicate checks.

    Example:
        >>> level, evidence = run_predicates(db, Context(vendor="sparx", version="17.1", model_id="test"))
        >>> print(level)
        5
        >>> print(evidence[0].predicate, evidence[0].passed)
        mml_1:count_tables True
    """
    evidence: List[EvidenceItem] = []
    for group, pid, fn in discover(groups):
        ok, details = fn(db, ctx)
        evidence.append(EvidenceItem(predicate=f"{group}:{pid}", passed=ok, details=details))

    # Simplest heuristic: number of passed predicates = maturity level.
    level = sum(1 for e in evidence if e.passed)
    return level, evidence
