# ------------------------------------------------------------
# Module: app/knowledge/criteria/runner.py
# Purpose: Execute all maturity predicates against parsed models.
# ------------------------------------------------------------

from __future__ import annotations

import traceback

from app.infra.utils.timing import ms_since, now_ns
from app.interface.api.v1.models import EvidenceItem
from app.interface.api.v1.serializers.analysis import normalize_results

from .loader import discover
from .protocols import Context, DbLike

# Soft SLA for predicate runtime (ms);
# used only for diagnostics ("SLOW" marker).
PREDICATE_SLA_MS = 100  # trigger "SLOW" note at 100ms


# Domain-specific exception so callers/tests can distinguish predicate failures from system errors.
class PredicateCrashed(Exception):
    def __init__(self, group, pid, err):
        super().__init__(f"{group}:{pid} crashed: {type(err).__name__}: {err}")


# Print-friendly duration formatting (sub-ms precision below 1.0ms, ints otherwise).
def _fmt_ms(ms: float) -> str:
    return f"{ms:.3f}" if ms < 1.0 else f"{int(round(ms))}"


def _to_api_results(evidence):
    out = []
    # sort by predicate; guard None → ""
    for e in sorted(evidence, key=lambda item: (getattr(item, "predicate", "") or "")):
        pid = e.predicate or ""
        # derive MML tier; fall back to 0
        try:
            tier = int(pid.split(":")[0].split("_")[1])
        except Exception:
            tier = 0
        # very compact UI-safe record (details redacted)
        out.append(
            {
                "predicate": pid.replace(":", "."),  # dotted for UI
                "tier": tier,
                "passed": bool(e.passed),
            }
        )
    return out


# Execute discovered predicates and return:
#   (maturity_level: int, evidence: list[EvidenceItem], levels: dict[str, dict])
# Error policy:
# - raise_on_error or fail_fast → raise on first predicate error (deterministic stop).
# - else → record error in evidence and continue.
def run_predicates(
    db: DbLike,
    ctx: Context,
    groups: list[str] | None = None,
    fail_fast: bool = True,
    raise_on_error: bool = True,
) -> tuple[int, list[EvidenceItem], dict[str, dict]]:
    """Run discovered predicates and return (maturity_level, evidence)."""
    evidence: list[EvidenceItem] = []
    details_by_id: dict[str, dict] = {}  # norm_id (with ':') -> details dict

    model_id = getattr(ctx, "model_id", None)
    vendor = getattr(ctx, "vendor", "")
    version = getattr(ctx, "version", "")

    print(
        f"[runner] begin model_id={model_id} vendor={vendor} version={version} groups={groups or 'ALL'}",
        flush=True,
    )

    # Import-time errors in predicates will raise immediately (strict=True).
    # If you want to aggregate import errors, lower strictness and handle here.
    loaded = discover(groups, strict=True)
    print(f"[runner] executing {len(loaded)} predicates…", flush=True)

    # Track which predicate IDs belong to each MML level and whether each passed.
    expected_by_level: dict[int, set[str]] = {}
    seen_by_level: dict[int, dict[str, bool]] = {}
    passed_total = 0

    for idx, (group, pid, fn) in enumerate(loaded, start=1):
        print(f"[runner] ({idx}/{len(loaded)}) RUN {group}:{pid}", flush=True)

        t0 = now_ns()
        status = "ok"
        err: Exception | None = None
        ok = False
        details_dict: dict = {}

        # Call the predicate; normalize 'details' to a plain dict.
        # On exception: either raise (fail-fast modes) or capture as failed evidence.
        try:
            ok, details = fn(db, ctx)
            details_dict = dict(details)
        except Exception as ex:
            # full traceback for debugging
            print(
                f"[runner] ERROR {group}:{pid} → {type(ex).__name__}: {ex}", flush=True
            )
            traceback.print_exc()
            if raise_on_error or fail_fast:
                raise PredicateCrashed(group, pid, ex)
            status = "error"
            err = ex
            ok = False
            details_dict = {}
        finally:
            # Measure runtime for SLA diagnostics; annotate "SLOW" if above threshold.
            dur_ms = ms_since(t0)  # float ms
            dur_str = _fmt_ms(dur_ms)
            slow = " SLOW" if dur_ms > PREDICATE_SLA_MS else ""
            if err:
                print(
                    f"[runner] DONE {group}:{pid} status={status} dur_ms={dur_str}{slow} ERROR={type(err).__name__}: {err}",
                    flush=True,
                )
            else:
                print(
                    f"[runner] DONE {group}:{pid} status={status} passed={ok} dur_ms={dur_str}{slow}",
                    flush=True,
                )

        # Stable predicate ID "mml_N:predicate_name" for evidence and UI mapping.
        norm_id = f"{group}:{pid}"
        if err is None:
            evidence.append(
                EvidenceItem(predicate=norm_id, passed=ok, details=details_dict)
            )

            # keep details for summary
            details_by_id[norm_id] = details_dict or {}

            # accumulate
            try:
                lvl = int(group.split("_")[1])
            except Exception:
                lvl = 0
            expected_by_level.setdefault(lvl, set()).add(norm_id)
            seen_by_level.setdefault(lvl, {})[norm_id] = ok
            if ok:
                passed_total += 1
        else:
            evidence.append(
                EvidenceItem(
                    predicate=norm_id, passed=False, details={}, error=str(err)
                )
            )
            details_by_id[norm_id] = {}
            try:
                lvl = int(group.split("_")[1])
            except Exception:
                lvl = 0
            expected_by_level.setdefault(lvl, set()).add(norm_id)
            seen_by_level.setdefault(lvl, {})[norm_id] = False

    # Maturity = highest level where *all* predicates at that level passed.
    # Stops at first level with any missing/failed predicate.
    maturity_level = 0
    for lvl in sorted(expected_by_level.keys()):
        want = expected_by_level[lvl]
        got = seen_by_level.get(lvl, {})
        all_passed = all(got.get(pid) is True for pid in want) and len(got) >= len(want)
        if not all_passed:
            break
        maturity_level = lvl
    print(
        f"[runner] complete model_id={model_id} maturity_level={maturity_level}/{len(loaded)}",
        flush=True,
    )

    # Build per-level breakdown (returned to caller so we don't leak locals)
    levels: dict[str, dict] = {}

    # Whitelist only UI-safe fields; strip any internal keys.
    ALLOWED_UI_KEYS = {"id", "passed", "counts", "summary", "source_tables"}

    for lvl in sorted(expected_by_level.keys()):
        want = expected_by_level[lvl]
        got = seen_by_level.get(lvl, {})
        passed = sum(1 for pid in want if got.get(pid) is True)
        present = len(got)
        failed = present - passed
        missing = len(want) - present

        preds = []
        for pid in sorted(want):
            det = details_by_id.get(pid, {}) or {}

            # Prefer a dotted, decorator-provided display ID if available; else derive from norm_id.
            friendly_id = det.get("probe_id") or pid.replace(":", ".")
            counts = dict(det.get("counts", {}) or {})
            measure = det.get("measure") or {}
            source_tables = list(det.get("source_tables", []) or [])

            summary = None
            # Normalize an optional universal summary {ok,total,fail} for simple UI bars.
            if isinstance(measure, dict) and ("ok" in measure or "total" in measure):
                ok = int(measure.get("ok", 0) or 0)
                total = int(measure.get("total", 0) or 0)
                summary = {"ok": ok, "total": total, "fail": max(0, total - ok)}

            # Build a NEW, UI-only dict and never merge from 'det'
            entry_clean = {
                "id": friendly_id,
                "passed": bool(got.get(pid)),
            }
            if counts:
                entry_clean["counts"] = counts
            if summary:
                entry_clean["summary"] = summary
            if source_tables:
                entry_clean["source_tables"] = source_tables

            # Final guard: drop any accidental keys
            entry_clean = {k: v for k, v in entry_clean.items() if k in ALLOWED_UI_KEYS}
            # Optional: sanity check in dev to catch leaks early
            # assert not any(k in entry_clean for k in ("probe_id","title")), entry_clean
            preds.append(entry_clean)

        levels[str(lvl)] = {
            "num_predicates": {
                "expected": len(want),
                "present": present,
                "passed": passed,
                "failed": failed,
                "missing": missing,
            },
            "predicates": preds,
        }
    return maturity_level, evidence, levels


# CLI: connect DuckDB, run predicates, and write summary.json (print-oriented diagnostics).
if __name__ == "__main__":
    import argparse
    from pathlib import Path

    import duckdb

    from app.infra.core import paths

    from .protocols import Context

    ap = argparse.ArgumentParser(
        description="Run maturity predicates and emit evidence.jsonl"
    )
    ap.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Path to model dir (…/data/models/<id>)",
    )
    ap.add_argument(
        "--vendor", type=str, default="", help="Vendor (e.g., sparx, cameo)"
    )
    ap.add_argument(
        "--version", type=str, default="", help="Vendor version (e.g., 17.1)"
    )
    args = ap.parse_args()

    model_dir = args.model_dir.resolve()
    model_id = model_dir.name

    db_path = model_dir / "model.duckdb"
    print(f"[runner] connect duckdb={db_path}", flush=True)
    con = duckdb.connect(str(db_path))
    con.execute("PRAGMA enable_object_cache=true;")

    ctx = Context(
        vendor=args.vendor or "",
        version=args.version or "",
        model_dir=model_dir,
        model_id=model_id,
        output_root=paths.MODELS_DIR,
    )

    level, evidence, levels = run_predicates(con, ctx)
    con.close()

    # --- write final summary.json (vendor/version-aware) ---
    import hashlib
    import json

    from app.infra.core import paths

    ej = paths.evidence_jsonl(model_id)
    docs = 0
    try:
        with ej.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    docs += 1
    except FileNotFoundError:
        docs = 0

    # deterministic fingerprint from predicate pass/fail + details keys
    fp_src = [
        {
            "id": e.predicate,
            "passed": bool(e.passed),
            "keys": sorted(list((e.details or {}).keys())),
        }
        for e in sorted(evidence, key=lambda x: (x.predicate or ""))
    ]

    # Deterministic fingerprint over (id, passed, detail-keys) for cache/diff in UI.
    fingerprint = hashlib.sha256(
        json.dumps(fp_src, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    summary = {
        "schema_version": "1.0",
        "model_id": model_id,
        "model": {"vendor": args.vendor or "", "version": args.version or ""},
        "maturity_level": level,
        "counts": {
            "predicates_total": len(evidence),
            "predicates_passed": sum(1 for e in evidence if e.passed),
            "predicates_failed": sum(1 for e in evidence if not e.passed),
            "evidence_docs": docs,
        },
        "fingerprint": fingerprint,
        "levels": levels,
    }
    paths.summary_json(model_id).write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    norm = normalize_results(evidence, redact=True)
    api_summary = {
        "schema_version": "1.0",
        "model": {"vendor": args.vendor or "", "version": args.version or ""},
        "maturity_level": level,
        "summary": {
            "total": len(norm),
            "passed": sum(1 for r in norm if r.passed),
            "failed": sum(1 for r in norm if not r.passed),
        },
        # dump Pydantic models to plain dicts for JSON
        "results": [r.model_dump(exclude_none=True) for r in norm],
    }

    (model_dir / "summary.api.json").write_text(
        json.dumps(api_summary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"[runner] exit maturity_level={level} evidence_items={len(evidence)} summary.json=written",
        flush=True,
    )
