# ------------------------------------------------------------
# Module: app/criteria/loader.py
# Purpose: Dynamically discover and import all predicate modules for maturity evaluation.
# ------------------------------------------------------------

"""Predicate discovery loader: finds and imports all maturity test modules.

Summary:
    Dynamically scans the `app.criteria` package for predicate modules organized
    by maturity levels (directories named `mml_1`, `mml_2`, etc.) and loads their
    `evaluate()` functions for execution by the predicate runner.

Details:
    - Predicate modules must follow the naming pattern `predicate_<name>.py`.
    - Each module should define:
        - `PREDICATE_ID`: short identifier for reporting (optional).
        - `evaluate(db, ctx) -> tuple[bool, dict]`: main entrypoint.
    - Discovery is recursive but limited to `mml_*`-prefixed directories.
    - Logging is verbose in debug mode to trace which predicates are loaded or skipped.

Developer Guidance:
    - Each predicate belongs to exactly one MML level directory (`app/criteria/mml_<N>/`).
    - When adding a new maturity level, create a matching directory and predicate modules.
    - Keep all predicate functions deterministic, fast, and side-effect-free.
    - Use `discover(groups)` to load predicates programmatically in tests or runners.
    - Unit test new predicates in isolation using a mock `sqlite3.Connection` and `Context`.
"""

import importlib
import logging
import pathlib
import pkgutil
import re
from typing import Iterable, List, Tuple, cast

from .protocols import Predicate

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
_BASE = pathlib.Path(__file__).parent
_MML = re.compile(r"^mml_\d+$")  # Match only maturity level folders like mml_1, mml_2
log = logging.getLogger("maturity.criteria.loader")


def discover(groups: Iterable[str] | None = None) -> List[Tuple[str, str, Predicate]]:
    """Discover and import all predicate modules across MML directories.

    Args:
        groups (Iterable[str] | None): Optional subset of groups (e.g. `["mml_1", "mml_3"]`).
            If provided, only those maturity level directories are scanned.
            If None, all mml_* groups are discovered.

    Returns:
        List[Tuple[str, str, Predicate]]:
            A list of (group, predicate_id, evaluate_function) tuples.

    Behavior:
        - Walks all submodules under `app.criteria/`.
        - Valid predicate modules must:
            - Be inside a folder matching `mml_<N>`.
            - Be named `predicate_<something>.py`.
            - Contain a callable `evaluate(db, ctx)` function.

    Example:
        >>> preds = discover(["mml_1"])
        >>> for group, pid, fn in preds:
        ...     ok, details = fn(db, ctx)
        ...     print(group, pid, ok)
    """
    wanted = set(groups) if groups else None
    results: List[Tuple[str, str, Predicate]] = []

    log.debug("Starting predicate discovery in %s (wanted=%s)", _BASE, wanted)

    # Walk through all modules in the criteria package
    for _, modname, ispkg in pkgutil.walk_packages([str(_BASE)], prefix=f"{__package__}."):
        if ispkg:
            log.debug("Skip package: %s", modname)
            continue

        parts = modname.split(".")
        if len(parts) < 4:
            log.debug("Skip: short module path (%s)", modname)
            continue

        group = parts[-2]
        if not _MML.fullmatch(group):
            log.debug("Skip: not mml_* group (%s)", modname)
            continue

        if wanted and group not in wanted:
            log.debug("Skip: group not requested (%s)", modname)
            continue

        if not parts[-1].startswith("predicate_"):
            log.debug("Skip: not predicate module (%s)", modname)
            continue

        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            log.exception("Import failed for %s: %s", modname, e)
            continue

        func = getattr(mod, "evaluate", None)
        pid = getattr(mod, "PREDICATE_ID", parts[-1])

        if callable(func):
            log.debug("Loaded predicate group=%s id=%s module=%s", group, pid, modname)
            results.append((group, pid, cast(Predicate, func)))
        else:
            log.debug("Skip: no evaluate() found in %s", modname)

    results.sort(key=lambda x: (x[0], x[1]))
    log.info("Predicate discovery complete. %d loaded.", len(results))
    return results
