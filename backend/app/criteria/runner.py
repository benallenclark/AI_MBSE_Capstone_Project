# ------------------------------------------------------------
# Module: app/criteria/runner.py
# Purpose: Execute all maturity predicates against parsed models.
# ------------------------------------------------------------

"""Execute all maturity predicates against a parsed model.

- Discovers predicates via `criteria.loader.discover()`.
- Each predicate returns `(passed: bool, details: dict)`.
- Returns maturity level = count of passed predicates and evidence list.
- Centralizes timing/logging; predicates stay pure.
"""

from __future__ import annotations

import logging
from typing import List  # or drop and use built-in list[...] everywhere
from .protocols import Context, DbLike
from .loader import discover
from app.api.v1.models import EvidenceItem
from app.utils.timing import now_ns, ms_since

log = logging.getLogger("maturity.criteria.runner")

PREDICATE_SLA_MS = 100  # trigger warning at 100ms

def run_predicates(
    db: DbLike,
    ctx: Context,
    groups: list[str] | None = None,
) -> tuple[int, list[EvidenceItem]]:
    """Run discovered predicates and return (maturity_level, evidence)."""
    evidence: list[EvidenceItem] = []

    model_id = getattr(ctx, "model_id", None)
    vendor = getattr(ctx, "vendor", "")
    version = getattr(ctx, "version", "")

    for group, pid, fn in discover(groups):
        t0 = now_ns()
        status = "ok"
        err: Exception | None = None
        ok = False
        details_dict: dict = {}

        try:
            ok, details = fn(db, ctx)
            details_dict = dict(details)
        except Exception as ex:
            status = "error"
            err = ex
            ok = False
            details_dict = {}
        finally:
            dur_ms = ms_since(t0)   # float ms
            dur_ms_str = f"{dur_ms:.3f}" if dur_ms < 1.0 else f"{int(round(dur_ms))}"
            log_level = logging.WARNING if dur_ms > PREDICATE_SLA_MS else logging.INFO
            log.log(
                log_level,
                "perf event=predicate group=%s id=%s model_id=%s vendor=%s version=%s "
                "status=%s dur_ms=%s%s",
                group, pid, model_id, vendor, version, status, dur_ms_str,
                "" if not err else f" err={type(err).__name__}:{err}",
            )
            if err:
                # stack trace once, at ERROR
                log.error("predicate_failed group=%s id=%s model_id=%s", group, pid, model_id, exc_info=True)

        if err is None:
            evidence.append(EvidenceItem(predicate=f"{group}:{pid}", passed=ok, details=details_dict))
        else:
            evidence.append(EvidenceItem(predicate=f"{group}:{pid}", passed=False, details={}, error=str(err)))

    maturity_level = sum(1 for e in evidence if e.passed)
    return maturity_level, evidence
