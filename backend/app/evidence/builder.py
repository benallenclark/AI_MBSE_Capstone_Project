# ------------------------------------------------------------
# Module: app/evidence/builder.py
# Purpose: Build and append Evidence v2 JSONL docs (summary + entity cards).
# ------------------------------------------------------------

from __future__ import annotations

import json
import pathlib
from typing import Any


# Normalize "mml_N:rule" → "mml_N.rule" (storage/display convention).
def _norm_probe_id(pid: str) -> str:
    return (pid or "").replace(":", ".").strip()


# Support both dict and @dataclass inputs without importing dataclasses at module load.
def _is_dataclass_instance(obj) -> bool:
    try:
        from dataclasses import is_dataclass

        return is_dataclass(obj)
    except Exception:
        return False


# Convert dict/dataclass/POJO to a narrow dict of allowed predicate fields.
# Avoid **-spreads to keep the shape predictable.
def _to_mapping(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if _is_dataclass_instance(obj):
        from dataclasses import asdict

        return asdict(obj)
    out: dict[str, Any] = {}
    for k in (
        "probe_id",
        "mml",
        "counts",
        "facts",
        "source_tables",
        "category",
        "rule",
        "severity",
        "measure",
        "refs",
    ):
        if hasattr(obj, k):
            out[k] = getattr(obj, k)
    return out


# Same pattern for per-entity facts; pull only known keys to avoid bloat.
def _fact_to_mapping(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if _is_dataclass_instance(obj):
        from dataclasses import asdict

        return asdict(obj)
    out: dict[str, Any] = {}
    for k in (
        "subject_type",
        "subject_id",
        "subject_name",
        "has_issue",
        "child_count",
        "tags",
        "meta",
        "refs",
        "quotes",
    ):
        if hasattr(obj, k):
            out[k] = getattr(obj, k)
    return out


# Emits newline-delimited JSON (JSONL) to model_dir/evidence/evidence.jsonl.
# Directory is created idempotently on instantiation.
class EvidenceBuilder:
    # Ensure per-model evidence dir exists and set output path once.
    def __init__(self, model_dir: pathlib.Path):
        self.model_dir = model_dir
        (self.model_dir / "evidence").mkdir(parents=True, exist_ok=True)
        self.out_path = self.model_dir / "evidence" / "evidence.jsonl"

    # Accepts dict/TypedDict/dataclass; writes 1 summary card + N entity cards.
    # Returns the list of emitted doc dicts (for caller display/tests).
    def emit(self, ctx: dict[str, Any], out: Any) -> list[dict[str, Any]]:
        """Accepts dict/TypedDict or dataclass; emits v2 summary + entity cards."""
        outd = _to_mapping(out)

        # Hard requirement: probe_id must be present after normalization.
        pid = _norm_probe_id(outd.get("probe_id", ""))
        if not pid:
            raise ValueError("PredicateOutput.probe_id is required")

        # Minimal provenance copied to metadata for scoping and retrieval.
        model_id = ctx["model_id"]
        vendor = ctx.get("vendor", "")
        version = ctx.get("version", "")
        mml = int(outd.get("mml", 0))
        group_id = f"{model_id}/{pid}"

        # 'summary' doc: compact overview per predicate.
        # - title/body are human-readable; UI can ignore/override them.
        # - metadata carries machine-usable fields (counts, source_tables, group_id).
        counts = dict(outd.get("counts", {}))
        summary_doc: dict[str, Any] = {
            "doc_id": f"{model_id}/{pid}",
            "probe_id": pid,
            "mml": mml,
            "doc_type": "summary",
            "title": f"{pid} summary",
            "body": f"{counts}",
            "ctx_hdr": f"[model={model_id} vendor={vendor} {version} mml={mml} probe={pid}]",
            "metadata": {
                "model_id": model_id,
                "vendor": vendor,
                "version": version,
                "maturity_level": mml,
                "counts": counts,
                "source_tables": list(outd.get("source_tables", [])),
                "group_id": group_id,
            },
        }

        # Optional classifier fields (if provided by the predicate payload).
        for k in ("category", "rule", "severity"):
            if k in outd:
                summary_doc["metadata"][k] = outd[k]
        # Optional normalized measure {ok,total} for quick UI bars.
        if "measure" in outd:
            summary_doc["metadata"]["measure"] = dict(outd["measure"])
        if "refs" in outd:
            summary_doc["metadata"]["refs"] = list(outd["refs"])

        docs: list[dict[str, Any]] = [summary_doc]

        # One doc per subject (block/port/etc.); includes tags/meta for filtering.
        for fobj in outd.get("facts") or []:
            f = _fact_to_mapping(fobj)
            subject_type = f.get("subject_type", "entity")
            subject_id = f.get("subject_id")
            subject_name = f.get("subject_name", "")
            has_issue = bool(f.get("has_issue", False))
            child_count = f.get("child_count")
            tags = list(f.get("tags", []))
            meta = dict(f.get("meta", {}))

            # Per-entity doc: stable doc_id combines model_id/probe_id/subject identifiers.
            # ctx_hdr is for quick grepping; structured data lives in 'metadata'.
            ent_doc: dict[str, Any] = {
                "doc_id": f"{model_id}/{pid}/{subject_type}/{subject_id}",
                "probe_id": pid,
                "mml": mml,
                "doc_type": subject_type,
                "title": self._default_title(
                    pid, subject_type, subject_name, tags, has_issue, child_count
                ),
                "body": self._default_body(
                    pid, subject_type, subject_name, has_issue, child_count
                ),
                "ctx_hdr": f"[model={model_id} vendor={vendor} {version} mml={mml} probe={pid}] {subject_type} '{subject_name}' (id={subject_id})",
                "metadata": {
                    "model_id": model_id,
                    "vendor": vendor,
                    "version": version,
                    "maturity_level": mml,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "has_issue": has_issue,
                    "child_count": child_count,
                    "tags": tags,
                    "meta": meta,
                    "source_tables": list(outd.get("source_tables", [])),
                    "group_id": group_id,
                },
            }
            for k in ("category", "rule", "severity"):
                if k in outd:
                    ent_doc["metadata"][k] = outd[k]

            # Prefer fact-level refs; fall back to predicate-level refs if absent.
            if "refs" in f:
                ent_doc["metadata"]["refs"] = list(f["refs"])
            elif "refs" in outd:
                ent_doc["metadata"]["refs"] = list(outd["refs"])

            docs.append(ent_doc)

        # Append mode by design (idempotent per run if caller guards duplicates).
        # For multi-process writers, consider file locks to avoid interleaving.
        with self.out_path.open("a", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
        return docs

    # Human-friendly title heuristic; special-cases common checks like block_has_port.
    def _default_title(
        self,
        pid: str,
        subject_type: str,
        subject_name: str,
        tags: list[str],
        has_issue: bool,
        child_count,
    ):
        frag: list[str] = []
        if child_count is not None:
            frag.append(f"({child_count})")
        if has_issue:
            frag.append("⚠")
        if pid.endswith(".block_has_port") and subject_type == "block":
            if child_count is None or child_count == 0:
                return f"Block missing ports: {subject_name}"
            return f"Block has ports: {subject_name}"
        return f"{subject_type.capitalize()}: {subject_name} {' '.join(frag)}".strip()

    # Short narrative "Finding … Implication … Action …" to seed UI text.
    def _default_body(
        self,
        pid: str,
        subject_type: str,
        subject_name: str,
        has_issue: bool,
        child_count,
    ):
        claim = ""
        if pid.endswith(".block_has_port") and subject_type == "block":
            if child_count is not None:
                claim = (
                    f"Finding: Block '{subject_name}' has {child_count} port(s)."
                    if not has_issue
                    else f"Finding: Block '{subject_name}' has 0 ports."
                )
        if not claim:
            claim = f"Finding: {subject_type} '{subject_name}'."
        return f"{claim} Implication: see maturity ladder guidance. Action: add/verify as required."
