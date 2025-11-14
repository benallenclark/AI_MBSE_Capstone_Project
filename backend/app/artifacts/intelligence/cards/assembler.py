# ------------------------------------------------------------
# Module: app/artifacts/intelligence/cards/assembler.py
# Purpose: Build and append Evidence v2 JSONL docs (summary + entity cards).
# ------------------------------------------------------------

"""Emit Evidence v2 documents (summary + entity cards) as newline-delimited JSON.

Responsibilities
----------------
- Normalize predicate payloads (dict/dataclass/POJO) to a predictable mapping.
- Write one summary document per predicate and one entity document per fact.
- Keep per-model evidence output in `model_dir/evidence/evidence.jsonl` (append-only).
- Provide human-friendly defaults for titles and bodies when the predicate omits them.

Notes
-----
- Output format is JSONL (one JSON document per line), UTF-8 encoded.
- Appends by design; callers should guard against duplicate emissions if needed.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from .coerce import fact_to_mapping, to_mapping

# -----------------------------
# FTS/UX helpers (plain ASCII)
# -----------------------------
# Use a text marker instead or whatever we prefer
WARN_MARKER = "[ISSUE]"

# Minimal domain keywords that help FTS match natural questions
_KEYWORDS_MAP: dict[str, list[str]] = {
    "block_has_port": ["interfaces", "ports", "connections"],
    "nonempty_names": ["naming", "names", "standards"],
}


def _keywords_for(pid: str, counts: dict | None, tags: list[str] | None) -> list[str]:
    """Return compact keyword hints for ctx_hdr to improve FTS recall."""
    base = (pid or "").split(".")[-1]
    ks: set[str] = set(_KEYWORDS_MAP.get(base, ()))
    c = counts or {}
    if "missing_ports" in c:
        ks.update({"missing", "no-ports"})
    if "unnamed" in c:
        ks.update({"unnamed", "empty-name"})
    if tags:
        ks.update(t for t in tags if isinstance(t, str))
    # keep short/stable ordering
    return sorted(ks)[:6]


def _summary_title(pid: str) -> str:
    """Readable summary titles (improves FTS + UX) with plain ASCII only."""
    base = (pid or "").split(".")[-1]
    if base == "block_has_port":
        return "Interfaces & Ports — coverage summary"
    if base == "nonempty_names":
        return "Naming — non-empty names summary"
    return f"{pid} summary"


def _build_structured_hint(
    pid: str, counts: dict | None, measure: dict | None
) -> dict[str, str]:
    """Derive a basic structured_hint from raw counts/measure.

    This is intentionally simple and deterministic:
    - observation: what the numbers say
    - implication: why that matters in MBSE terms (rough, generic)
    - recommendation: what to do next

    Predicate-specific overrides can be added here over time.
    """
    observation = ""
    implication = ""
    recommendation = ""

    counts = counts or {}
    measure = measure or {}

    # Generic "ok/total" style metrics
    ok = measure.get("ok") if measure else None
    total = None
    if measure:
        total = measure.get("total") or measure.get("total_checks")

    if ok is not None and total:
        ratio = ok / total
        observation = f"{ok} of {total} checks passed (~{ratio:.0%})."

        if ok == total:
            # All checks passed
            implication = (
                "This area currently satisfies all defined checks. It is not a bottleneck"
                " for model maturity based on the current criteria."
            )
            recommendation = (
                "Keep this area stable and use it as a reference pattern when improving"
                " weaker parts of the model."
            )
        elif ratio < 0.5:
            implication = (
                "Overall this area is weak, a high-priority gap in model maturity,"
                " and likely to cause rework later."
            )  #
            recommendation = (
                "Prioritize bringing the failing checks in this area up to a basic"
                " acceptable standard. This is a key fix for improving maturity."
            )  #
        elif ratio < 0.8:
            implication = (
                "This area is partially covered but still has notable gaps impacting"
                " overall model maturity."
            )  #
            recommendation = (
                "Incrementally address the failing checks here to improve maturity,"
                " especially the ones that affect interfaces, traceability, or safety."
            )  #
        else:
            implication = (
                "This area is largely in good shape, with only minor gaps."
                " This meets a good level of maturity."
            )  #
            recommendation = (
                "Clean up the remaining failing checks, but do not over-optimize this"
                " area at the expense of more critical maturity gaps elsewhere."
            )  #

    # Special-case for block_has_port style predicates
    if "blocks_total" in counts and "with_ports" in counts:
        blocks_total = counts["blocks_total"] or 0
        with_ports = counts["with_ports"] or 0
        missing_ports = counts.get("missing_ports", max(blocks_total - with_ports, 0))
        ratio = (with_ports / blocks_total) if blocks_total else 0.0

        observation = (
            f"{with_ports} of {blocks_total} blocks (~{ratio:.0%}) have ports; "
            f"{missing_ports} blocks have no explicit ports."
        )
        implication = (
            "Most block interfaces are implicit or undefined, which makes integration"
            " ambiguous. This is a critical gap in model maturity."  #
        )
        recommendation = (
            "Review each Block and add explicit Ports for its external interfaces so"
            " that connections, flows, and responsibilities are clear. This is a"
            " high-impact fix to improve model maturity."  #
        )

    # Fallback if we couldn't derive anything specific
    if not observation:
        observation = "This predicate produced counts and/or measures, but no custom hint is defined yet."
    if not implication:
        implication = (
            "Without a custom implication, treat this as an indicator of model"
            " hygiene or completeness, which impacts maturity."
        )  #
    if not recommendation:
        recommendation = (
            "Review this area of the model and bring it in line with your team's"
            " MBSE standards to improve maturity."
        )  #

    return {
        "observation": observation,
        "implication": implication,
        "recommendation": recommendation,
    }


def _norm_probe_id(pid: str) -> str:
    """Normalize probe IDs to storage/display form.

    Converts "mml_N:rule" → "mml_N.rule" and trims whitespace.
    """
    return (pid or "").replace(":", ".").strip()


class EvidenceBuilder:
    """Append Evidence v2 JSONL documents for a single model.

    Notes
    -----
    - Creates `model_dir/evidence/` if missing (idempotent).
    - Writes to `evidence.jsonl` in append mode (no locking here).
    """

    def __init__(self, model_dir: pathlib.Path):
        """Initialize builder for a given `model_dir` and ensure output path exists."""
        self.model_dir = model_dir
        (self.model_dir / "evidence").mkdir(parents=True, exist_ok=True)
        self.out_path = self.model_dir / "evidence" / "evidence.jsonl"

    def emit(self, ctx: dict[str, Any], out: Any) -> list[dict[str, Any]]:
        """Emit one summary + N entity documents for a predicate run.

        Parameters
        ----------
        ctx : dict
            Minimal provenance: requires `model_id`; may include `vendor`, `version`.
        out : Any
            Predicate output (dict/dataclass/POJO). Only known fields are persisted.

        Returns
        -------
        list[dict[str, Any]]
            The list of documents that were written (summary first, then entities).

        Notes
        -----
        - Raises ValueError if `probe_id` is missing after normalization.
        - `mml` is treated as an integer maturity level (0 if omitted).
        - Side effect: appends to `evidence.jsonl` with compact separators.
        """
        outd = to_mapping(out)

        # Predicate-level status: did this check pass?
        passed = bool(outd.get("passed", False))

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
        keywords = _keywords_for(pid, counts, list(outd.get("tags", [])))
        summary_doc: dict[str, Any] = {
            "doc_id": f"{model_id}/{pid}",
            "probe_id": pid,
            "mml": mml,
            "doc_type": "summary",
            "title": _summary_title(pid),
            "body": f"{counts}",
            "ctx_hdr": (
                f"[model={model_id} vendor={vendor} {version} mml={mml} probe={pid}] "
                + (f"keywords: {' '.join(keywords)}" if keywords else "")
            ).strip(),
            "metadata": {
                "model_id": model_id,
                "vendor": vendor,
                "version": version,
                "maturity_level": mml,
                "counts": counts,
                "source_tables": list(outd.get("source_tables", [])),
                "group_id": group_id,
                "status": "pass" if passed else "fail",
                "keywords": keywords,
            },
        }

        # Optional classifier fields (if provided by the predicate payload).
        for k in ("category", "rule", "severity", "domain"):
            if k in outd:
                summary_doc["metadata"][k] = outd[k]

        # Optional normalized measure {ok,total} for quick UI bars.
        measure = None
        if "measure" in outd:
            measure = dict(outd["measure"])
            summary_doc["metadata"]["measure"] = dict(outd["measure"])
            if measure.get("ok") is not None and measure.get("total") is not None:
                # Override 'passed' based on the measure
                passed = measure["ok"] == measure["total"]
        else:
            measure = None

        # Optional refs
        if "refs" in outd:
            summary_doc["metadata"]["refs"] = list(outd["refs"])

        # Derive a structured_hint the LLM can use directly.
        structured_hint = _build_structured_hint(pid, counts, measure)
        summary_doc["metadata"]["structured_hint"] = structured_hint

        docs: list[dict[str, Any]] = [summary_doc]

        # One doc per subject (block/port/etc.); includes tags/meta for filtering.
        for fobj in outd.get("facts") or []:
            f = fact_to_mapping(fobj)
            subject_type = f.get("subject_type", "entity")
            subject_id = f.get("subject_id")
            subject_name = f.get("subject_name", "")
            has_issue = bool(f.get("has_issue", False))
            child_count = f.get("child_count")
            tags = list(f.get("tags", []))
            meta = dict(f.get("meta", {}))
            f_keywords = _keywords_for(pid, counts, tags)

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
                "ctx_hdr": (
                    f"[model={model_id} vendor={vendor} {version} mml={mml} probe={pid}] "
                    f"{subject_type} '{subject_name}' (id={subject_id}) "
                    + (f"keywords: {' '.join(f_keywords)}" if f_keywords else "")
                ).strip(),
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
                    "status": "issue" if has_issue else "ok",
                    "keywords": f_keywords,
                },
            }
            for k in ("category", "rule", "severity", "domain"):
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
        """Create a short, human-friendly title for an entity document.

        Notes
        -----
        - Special-cases `*.block_has_port` when subject_type == "block".
        - Includes child count (if present) and a warning glyph when `has_issue` is True.
        """
        frag: list[str] = []
        if child_count is not None:
            frag.append(f"({child_count})")
        if has_issue:
            frag.append(WARN_MARKER)
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
        """Generate a compact narrative body for the entity document.

        Format
        ------
        "Finding … Implication … Action …" with a simple rule-aware message.

        Notes
        -----
        - Special handling for `*.block_has_port` to note port count explicitly.
        - Keeps language generic so UIs can augment or replace this text.
        """
        claim = ""
        if pid.endswith(".block_has_port") and subject_type == "block":
            if child_count is not None:
                claim = (
                    f"Finding: Block '{subject_name}' has {child_count} port(s)."
                    if not has_issue
                    else f"Finding: Block '{subject_name}' has 0 ports."
                )
        elif pid.endswith(".nonempty_names"):
            claim = (
                f"Finding: {subject_type} '{subject_name}' has an empty name."
                if has_issue
                else f"Finding: {subject_type} '{subject_name}' is properly named."
            )
        if not claim:
            claim = f"Finding: {subject_type} '{subject_name}'."
        return f"{claim} Implication: see maturity ladder guidance. Action: add/verify as required."
