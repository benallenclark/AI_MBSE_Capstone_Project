# bff_summary.py
import re
from typing import Any

ANALYZE_VERSION = "1"
MML_MAX_LEVEL = 10  # clamp to 0..10

# Optional: central registry for legacy rule IDs without mml in the card
# Fill with your real mapping as you assign levels.
RULE_MML: dict[str, int] = {
    "MAT-001": 1,  # Viewpoints must have a Stakeholder
    "MAT-002": 4,  # Blocks must satisfy at least one Requirement
    "MAT-003": 7,  # Requirements must be verified by a Test Case
    # ...
}


def _clamp(n: int, lo: int = 0, hi: int = MML_MAX_LEVEL) -> int:
    try:
        return max(lo, min(hi, int(n)))
    except Exception:
        return 0


def _mml_from_id(rule_id: str) -> int:
    # regex fallback, e.g. "mml_3" / "mml-3" / "mml3"
    m = re.search(r"\bmml[_-]?(\d+)\b", rule_id, re.IGNORECASE) or re.search(
        r"mml(\d+)", rule_id, re.IGNORECASE
    )
    return _clamp(m.group(1)) if m else 0


def _infer_mml(rule_id: str, explicit: Any | None) -> int:
    # 1) explicit field on the card
    if isinstance(explicit, int):
        return _clamp(explicit)
    if isinstance(explicit, str) and explicit.isdigit():
        return _clamp(int(explicit))
    # 2) registry
    if rule_id in RULE_MML:
        return _clamp(RULE_MML[rule_id])
    # 3) regex from id
    return _mml_from_id(rule_id)


def _clean_details(d: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k in ("violation_count", "counts", "description", "source_tables"):
        if k in d and d[k] is not None:
            out[k] = d[k]
    if isinstance(d.get("violations"), list) and d["violations"]:
        out["violations_sample"] = d["violations"][:3]  # keep top 3 only
    return out


def _summary(results: list[dict[str, Any]]) -> dict[str, int]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed") is True)
    failed = total - passed
    return {"total": total, "passed": passed, "failed": failed}


def _maturity_level(
    results: list[dict[str, Any]], max_level: int = MML_MAX_LEVEL
) -> int:
    # Gate: L is achieved only if all rules with mml ≤ L passed
    by_level: dict[int, list[dict[str, Any]]] = {}
    for r in results:
        by_level.setdefault(int(r.get("mml", 0)), []).append(r)

    level = 0
    for L in range(1, max_level + 1):
        needed = []
        for l in range(1, L + 1):
            needed.extend(by_level.get(l, []))
        if needed and all(rr.get("passed") is True for rr in needed):
            level = L
        else:
            break

    # If everything is mml=0 (or empty), fall back to pass-rate scaling.
    if level == 0 and any(int(r.get("mml", 0)) == 0 for r in results):
        s = _summary(results)
        if s["total"] > 0:
            level = _clamp(round((s["passed"] / s["total"]) * max_level), 0, max_level)
    return level


def from_analyze_response(evidence: dict[str, Any]) -> dict[str, Any]:
    cleaned_results = []
    for r in evidence.get("results", []):
        details = r.get("details") or {}
        cleaned_results.append(
            {
                "id": r.get("id", "rule"),
                "mml": _infer_mml(str(r.get("id", "")), r.get("mml")),
                "passed": bool(r.get("passed", False)),
                "details": _clean_details(details),
                **({"error": r["error"]} if r.get("error") else {}),
            }
        )
    s = _summary(cleaned_results)
    m = _maturity_level(cleaned_results)
    return {
        "schema_version": ANALYZE_VERSION,
        "model": {
            "vendor": str(evidence.get("model", {}).get("vendor") or "unknown"),
            "version": str(evidence.get("model", {}).get("version") or "unknown"),
            "model_id": str(evidence.get("model", {}).get("model_id") or "unknown"),
        },
        "maturity_level": m,
        "summary": s,
        "results": cleaned_results,
    }


def from_cards(
    cards: list[dict[str, Any]], vendor="unknown", version="unknown", model_id="unknown"
) -> dict[str, Any]:
    # Group by rule id; prefer explicit mml else map else regex
    groups: dict[str, dict[str, Any]] = {}
    for c in cards:
        rid = str(
            c.get("probe_id")
            or c.get("predicate_id")
            or c.get("rule_id")
            or c.get("id")
            or "rule"
        )
        g = groups.setdefault(rid, {"id": rid, "mml": 0, "passed": None, "details": {}})

        # infer & store mml (prefer explicit)
        g["mml"] = _infer_mml(rid, c.get("mml"))

        # infer pass/fail
        if isinstance(c.get("passed"), bool):
            g["passed"] = c["passed"]
        elif "status" in c:
            g["passed"] = str(c["status"]).upper() == "PASS"

        # details, but slimmed
        g["details"] = _clean_details(
            {
                k: c.get(k)
                for k in (
                    "violation_count",
                    "violations",
                    "counts",
                    "description",
                    "source_tables",
                )
                if k in c
            }
        )

    results = [
        {
            "id": rid,
            "mml": _clamp(g.get("mml", 0)),
            "passed": bool(g["passed"]) if g["passed"] is not None else False,
            "details": g["details"] or {},
        }
        for rid, g in groups.items()
    ]
    return {
        "schema_version": ANALYZE_VERSION,
        "model": {"vendor": vendor, "version": version, "model_id": model_id},
        "maturity_level": _maturity_level(results),
        "summary": _summary(results),
        "results": results,
    }


def transform(
    evidence: Any, vendor="unknown", version="unknown", model_id="unknown"
) -> dict[str, Any]:
    # Already AnalyzeResponse shape? normalize & strip
    if isinstance(evidence, dict) and all(
        k in evidence for k in ("schema_version", "model", "summary", "results")
    ):
        return from_analyze_response(evidence)

    # List of cards?
    if isinstance(evidence, list):
        return from_cards(evidence, vendor, version, model_id)

    # Legacy “maturity report” (meta/results/status schema)
    if isinstance(evidence, dict) and "results" in evidence:
        results = []
        for idx, r in enumerate(evidence["results"]):
            rid = str(r.get("rule_id") or r.get("id") or f"rule_{idx}")
            mml = _infer_mml(rid, r.get("mml"))
            status = str(r.get("status", "")).upper()
            passed = (
                True
                if status == "PASS"
                else False
                if status == "FAIL"
                else bool(r.get("passed", False))
            )
            results.append(
                {
                    "id": rid,
                    "mml": mml,
                    "passed": passed,
                    "details": _clean_details(r),
                }
            )
        out = {
            "schema_version": ANALYZE_VERSION,
            "model": {
                "vendor": vendor,
                "version": version,
                "model_id": str(evidence.get("meta", {}).get("session_id") or model_id),
            },
            "maturity_level": _maturity_level(results),
            "summary": _summary(results),
            "results": results,
        }
        return out

    # Unknown shape: render a safe placeholder
    return {
        "schema_version": ANALYZE_VERSION,
        "model": {"vendor": vendor, "version": version, "model_id": model_id},
        "maturity_level": 0,
        "summary": {"total": 1, "passed": 0, "failed": 1},
        "results": [
            {
                "id": "unrecognized_evidence_format",
                "mml": 0,
                "passed": False,
                "details": {"note": "update transformer for this evidence shape"},
            }
        ],
    }
