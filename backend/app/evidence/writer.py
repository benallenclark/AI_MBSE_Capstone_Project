# ---------------------------------------------------------------------
# backend/app/evidence/writer.py — Evidence v2 only
# Purpose: Single, canonical entrypoints for emitting Evidence v2 cards.
# ---------------------------------------------------------------------
from __future__ import annotations
from typing import Dict, Any, Iterable, List
import pathlib
from .types import PredicateOutput
from .builder import EvidenceBuilder

# Emits Evidence v2 cards for one predicate into `<model_dir>/evidence`.
# `ctx` = small, JSON-serializable metadata (model/vendor/version, probe info).
# Returns the emitted card dicts so callers can log/test without rereading from disk.
def emit_evidence(model_dir: pathlib.Path, ctx: Dict[str, Any], output: PredicateOutput) -> List[Dict[str, Any]]:

    # One-off builder bound to `model_dir`; handles JSONL append and directory layout.
    # If `output` is malformed or evidence dir missing, this may raise—caller decides retry vs. fail.
    return EvidenceBuilder(model_dir).emit(ctx, output)

# Emits multiple predicate outputs in order (no parallelism).
# Returns a flat list; order matches the iteration order of `outputs`.
def emit_batch(model_dir: pathlib.Path, ctx: Dict[str, Any], outputs: Iterable[PredicateOutput]) -> List[Dict[str, Any]]:
    
    # Avoids reinitializing FS state/handles for each output; faster and less error-prone at scale.
    builder = EvidenceBuilder(model_dir)
    docs: List[Dict[str, Any]] = []
    
    # Preserves iterator order, keeping logs/snapshots stable as evidence is appended to disk.
    for out in outputs:
        docs.extend(builder.emit(ctx, out))
    return docs

# Creates a columnar Parquet twin of `evidence.jsonl` for faster analytics/filters.
# Run after emits complete; it does not track later appends.
def mirror_jsonl_to_parquet(model_dir: pathlib.Path) -> pathlib.Path:
    import duckdb
    ev_dir = model_dir / "evidence"
    
    # Assumes `evidence.jsonl` exists; DuckDB will error if missing.
    # `.as_posix()` avoids Windows backslash escaping issues inside the SQL string.
    src = (ev_dir / "evidence.jsonl").as_posix()
    
    dst = (ev_dir / f"{model_dir.name}_evidence.parquet").as_posix()
    con = duckdb.connect()
    
    # `read_json_auto` infers types; mixed shapes across cards may widen fields to STRING.
    # Depending on DuckDB/version, COPY may overwrite `dst`—use a unique name if you need history.
    con.execute(f"COPY (SELECT * FROM read_json_auto('{src}')) TO '{dst}' (FORMAT PARQUET);")
    
    con.close()
    
    # Returns the Parquet path so callers can hand it directly to analytics code.
    return pathlib.Path(dst)
