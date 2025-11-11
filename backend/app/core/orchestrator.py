# ------------------------------------------------------------
# Module: app/core/orchestrator.py
# Purpose: Single entry point to run the pipeline end-to-end
#          (ingest → IR → predicates → summary → RAG index).
# ------------------------------------------------------------

from __future__ import annotations
import hashlib, subprocess, sys, json
from dataclasses import dataclass
from pathlib import Path
from app.core import paths

# Run a subprocess and stream its stdout line-by-line.
# - Fails fast on non-zero exit codes.
# - Use for long-running steps to surface progress in real time.
def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    # Stream child output live; still fail loudly on non-zero exit.
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        assert p.stdout is not None
        for line in p.stdout:
            print(line, end="", flush=True)
    finally:
        rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"cmd failed ({rc}): {' '.join(cmd)}")

# Derive a stable short id from file content (sha256[:8]); enables idempotent runs.
def compute_model_id(xml_path: Path) -> str:
    h = hashlib.sha256()
    with open(xml_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]

# Minimal artifact manifest returned to callers (paths as strings).
@dataclass(frozen=True)
class RunResult:
    model_id: str
    model_dir: Path
    artifacts: dict

# Single source of truth for the pipeline:
# - Idempotent per model_id; pass overwrite=True to re-ingest XML.
# - vendor/version forwarded to predicate runner for context.
# - Raises if predicates emit no evidence (fast feedback on broken runs).
def run(*, model_id: str, xml_path: Path | None = None, overwrite: bool = False,
        build_rag: bool = True, run_predicates: bool = True,
        vendor: str = "", version: str = "") -> RunResult:
    
    # Ensure the standard per-model directory layout exists (e.g., evidence/, parquet/).
    model_dir = paths.ensure_model_dirs(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Ingest XML → per-model DuckDB (optionally overwrite existing artifacts).
    if xml_path is not None:
        cmd = [sys.executable, "-m", "app.ingest.loader_duckdb", "--xml", str(xml_path), "--model-id", model_id]
        if overwrite:
            cmd.append("--overwrite")
        _run(cmd)

    # Step 2: Build IR from the ingested tables.
    _run([sys.executable, "-m", "app.ingest.build_ir", "--model-dir", str(model_dir)])

    # Step 3: Run deterministic predicates (produces evidence.jsonl and optional summary).
    if run_predicates:
        cmd = [sys.executable, "-u", "-m", "app.criteria.runner", "--model-dir", str(model_dir)]
        if vendor:  cmd += ["--vendor", vendor]
        if version: cmd += ["--version", version]
        _run(cmd)

    # Hard guardrail: predicates must emit evidence; fail early if empty.
    ej = paths.evidence_jsonl(model_id)
    if not ej.exists() or ej.stat().st_size == 0:
        raise RuntimeError(f"predicates emitted no evidence: expected {ej.as_posix()}")

    # If the runner didn't write a summary, emit a minimal stub for UI consumption.
    sj = paths.summary_json(model_id)
    if not sj.exists():
        try:
            total_docs = 0
            with ej.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        total_docs += 1
            summary = {
                "schema_version": "1.0",
                "model_id": model_id,
                "maturity_level": None,
                "counts": {"evidence_docs": total_docs},
                "fingerprint": None,
            }
            sj.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # non-fatal

    # Step 4: Build per-model RAG index (rag.sqlite) next to evidence.
    rag_db = None
    if build_rag:
        _run([sys.executable, "-m", "app.rag.bootstrap_index", str(ej)], cwd=model_dir)
        rag_db = paths.rag_sqlite(model_id)

    # Return paths to key artifacts so callers (API/tests) can link or inspect.
    artifacts = {
        "xml": str(xml_path) if xml_path else None,
        "duckdb": str(paths.duckdb_path(model_id)),
        "evidence_jsonl": str(ej),
        "rag_sqlite": str(rag_db) if rag_db else None,
        "model_dir": str(model_dir),
    }
    return RunResult(model_id=model_id, model_dir=model_dir, artifacts=artifacts)
