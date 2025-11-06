# ------------------------------------------------------------
# Module: app/criteria/loader.py
# Purpose: Dynamically discover and import all predicate modules for maturity evaluation.
# ------------------------------------------------------------

from __future__ import annotations
import importlib
import pathlib
import pkgutil
import re
import traceback
from typing import Iterable, List, Tuple, cast
from .protocols import Predicate


# Discovery roots & filters:
# - Only scan immediate package tree under app.criteria.
# - Accept folders named mml_<N>; ignore anything else (e.g., helpers).
_BASE = pathlib.Path(__file__).parent
_MML = re.compile(r"^mml_\d+$")  # Match only maturity level folders like mml_1, mml_2

# Discover predicate modules and return [(group, predicate_id, evaluate_fn)].
# - groups: optional {'mml_1', 'mml_2', ...} subset filter.
# - strict=True: abort on first import error; False: collect all loadable predicates.
def discover(groups: Iterable[str] | None = None, strict: bool = True) -> List[Tuple[str, str, Predicate]]:
    wanted = set(groups) if groups else None
    results: List[Tuple[str, str, Predicate]] = []

    print(f"[loader] start discovery base={_BASE} wanted={sorted(wanted) if wanted else 'ALL'}", flush=True)

    # Walk only this package's filesystem path; prefix ensures fully-qualified imports.
    import_errors = []
    for _, modname, ispkg in pkgutil.walk_packages([str(_BASE)], prefix=f"{__package__}."):
        if ispkg:
            # packages are just containers; skip
            continue

        # Expected layout: app.criteria.{mml_N}.predicate_*
        # Skip any modules that don't match the depth or naming convention.
        parts = modname.split(".")
        if len(parts) < 4:
            # Expect: app.criteria.mml_X.predicate_*
            continue

        group = parts[-2]
        if not _MML.fullmatch(group):
            continue

        if wanted and group not in wanted:
            continue

        if not parts[-1].startswith("predicate_"):
            continue

        # Import each candidate in isolation; side effects in module top-level are on the module.
        # On failure: print diagnostic and either raise (strict) or continue.
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f"[loader] IMPORT FAILED: {modname}: {e}", flush=True)
            import_errors.append((modname, e))
            traceback.print_exc()
            if strict:
                raise
            continue

        # Contract: module must expose `evaluate(ctx, con) -> EvidenceItem|Iterable[EvidenceItem]`.
        # ID source: PREDICATE_ID if present, else module basename.
        func = getattr(mod, "evaluate", None)
        pid = getattr(mod, "PREDICATE_ID", parts[-1])

        if callable(func):
            print(f"[loader] loaded {group}:{pid} ({modname})", flush=True)
            results.append((group, pid, cast(Predicate, func)))
        else:
            # No evaluate() — skip quietly
            continue

    # Deterministic order: sort by (group, predicate_id) for stable runs and tests.
    results.sort(key=lambda x: (x[0], x[1]))
    summary = [f"{g}:{p}" for (g, p, _) in results]
    
    # Print-oriented diagnostics (intended for CLI); see non-print variant for logging.
    print(f"[loader] discovery complete: {len(results)} loaded -> {summary}", flush=True)
    if import_errors and strict:
        raise RuntimeError(f"Predicate import failures: {[(m,type(e).__name__) for m,e in import_errors]}")
    return results
