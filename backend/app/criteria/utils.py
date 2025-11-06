# ------------------------------------------------------------
# Module: app/criteria/utils.py
# Purpose: Predicate helper utilities (ID inference + decorator to emit evidence).
# ------------------------------------------------------------

from __future__ import annotations
import re
from pathlib import Path
from typing import Callable, Dict, Any, Tuple, List, cast
from app.evidence.writer import emit_evidence
from app.evidence.types import PredicateOutput, Fact

# Accept only folders named mml_<N>; used to infer maturity level from filesystem layout.
_mml_re = re.compile(r"^mml_(\d+)$")

# Infer ("mml_N", "predicate_name", N) from the module's file path.
# Raises ValueError if the folder convention is violated.
def infer_ids(module_file: str) -> Tuple[str, str, int]:
    """
    Infer (group, predicate_id, mml) from filesystem:
      .../criteria/mml_2/predicate_block_has_ports.py
      -> ("mml_2", "block_has_ports", 2)
    """
    p = Path(module_file).resolve()
    group = p.parent.name                      # "mml_2"
    m = _mml_re.match(group)
    if not m:
        raise ValueError(f"Cannot infer MML from folder '{group}' (expected mml_<n>)")
    mml = int(m.group(1))
    pred = p.stem                               # "predicate_block_has_ports"
    if pred.startswith("predicate_"):
        pred = pred[len("predicate_"):]
    return group, pred, mml

# Turn a lightweight 'core(db, ctx) -> payload' into a full predicate:
# - infers IDs from the module path,
# - emits Evidence v2 via writer.emit_evidence(),
# - returns (passed, details) for the runner.
def predicate(core: Callable[[Any, Any], Dict[str, Any]]) -> Callable[[Any, Any], tuple[bool, Dict[str, Any]]]:
    def evaluate(db, ctx):
        # Expected keys from core(): passed:bool, counts:dict, facts:list, source_tables:list, (optional) category, rule, severity, measure, refs.
        payload = core(db, ctx) or {}
        passed = bool(payload.get("passed", False))
        
        # Normalize shapes and types for stable serialization and TypedDict compatibility.
        counts: Dict[str, Any] = dict(payload.get("counts", {}))
        facts:  List[Fact]     = cast(List[Fact], list(payload.get("facts", [])))
        src:    List[str]      = [str(s) for s in list(payload.get("source_tables", []))]

        # Use the core() file path to derive IDs—works in normal installs; 
        # zipimport/pyinstaller may need special handling.
        group, pid, mml = infer_ids(core.__code__.co_filename)
        
        # Dotted probe_id used across evidence and UI (e.g., "mml_2.block_has_port").
        probe_id = f"{group}.{pid}"

        # Emit evidence.jsonl through the canonical writer
        # Only include context fields required for evidence provenance.
        ctx_dict = {
            "model_id": getattr(ctx, "model_id", ""),
            "vendor": getattr(ctx, "vendor", ""),
            "version": getattr(ctx, "version", ""),
        }

        # Build the evidence payload explicitly to keep the TypedDict shape narrow and predictable.
        output: PredicateOutput = {
            "probe_id": probe_id,         # e.g., "mml_2.block_has_port"
            "mml": int(mml),
            "counts": counts,             # Dict[str, Any]
            "facts": facts,               # List[Fact]
            "source_tables": src,         # List[str]
        }

        # Optional fields are set individually to avoid widening the TypedDict type.
        if "category" in payload:
            output["category"] = cast(Any, payload["category"])
        if "rule" in payload:
            output["rule"] = cast(Any, payload["rule"])
        if "severity" in payload:
            output["severity"] = cast(Any, payload["severity"])
        if "measure" in payload:
            output["measure"] = cast(Any, payload["measure"])
        if "refs" in payload:
            output["refs"] = cast(Any, payload["refs"])

        # Returns emitted document metadata (ids/titles), used for downstream display.
        docs = emit_evidence(Path(ctx.model_dir), ctx_dict, output)

        # Compact, UI-safe details returned to the runner; 
        # avoid large blobs or raw SQL results.
        details = {
            "probe_id": probe_id,
            "mml": mml,
            "passed": passed,
            "counts": counts,
            "source_tables": src,
            "evidence": docs,  # ids/titles/etc. of emitted docs
        }
        return passed, details
    return evaluate
