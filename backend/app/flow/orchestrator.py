# ------------------------------------------------------------
# Module: app/flow/orchestrator.py
# Purpose: Single entry point to run the pipeline end-to-end
#          (ingest → IR → predicates → summary → RAG index).
# ------------------------------------------------------------

"""Run the full model pipeline for a given model_id.

Responsibilities
----------------
- Create/validate the per-model directory layout.
- Ingest XML into DuckDB (optional overwrite).
- Build the IR tables required by downstream steps.
- Execute predicates to produce evidence and (optionally) a summary.
- Enforce a hard guardrail that evidence exists before continuing.
- Build the per-model RAG index adjacent to evidence artifacts.
- Return a lightweight manifest of key artifact paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.infra.core import paths
from app.infra.utils.maintenance import post_run_cleanup, pre_run_cleanup

log = logging.getLogger(__name__)


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    """Run a subprocess and stream its stdout line-by-line.

    Notes
    -----
    - Fails fast on non-zero exit codes (raises RuntimeError).
    - Streams combined stdout/stderr in real time (good for long steps).
    - `cwd` changes the working directory for the child process.
    """
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


def compute_model_id(xml_path: Path) -> str:
    """Return a stable short ID (sha256[:8]) derived from XML file bytes.

    Notes
    -----
    - Reads the file in 1 MiB chunks (memory-friendly for large inputs).
    - Output is deterministic; use as an idempotent run key.
    """
    h = hashlib.sha256()
    with open(xml_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


@dataclass(frozen=True)
class RunResult:
    """Minimal manifest of a completed run (friendly for API/tests).

    Attributes
    ----------
    model_id : str
        The short, deterministic ID for this model.
    model_dir : Path
        Root directory for all per-model artifacts.
    artifacts : dict
        Paths to key outputs (values are strings; some may be None).
    """

    model_id: str
    model_dir: Path
    artifacts: dict


def run(
    *,
    model_id: str,
    xml_path: Path | None = None,
    overwrite: bool = False,
    build_rag: bool = True,
    run_predicates: bool = True,
    vendor: str = "",
    version: str = "",
) -> RunResult:
    """Execute the pipeline end-to-end for a given model_id.

    Steps
    -----
    1) (Optional) Ingest XML → DuckDB (honors `overwrite`).
    2) Build IR from ingested tables.
    3) Run predicates to produce evidence.jsonl (and optional summary).
    4) Ensure evidence exists (hard guardrail).
    5) If no summary exists, write a minimal stub for UI consumption.
    6) (Optional) Build the per-model RAG SQLite index.

    Parameters
    ----------
    model_id : str
        Deterministic identifier for the model (e.g., from `compute_model_id`).
    xml_path : Path | None
        XML source to ingest. If None, reuse existing ingested data.
    overwrite : bool
        If True, re-ingest and overwrite prior artifacts for this model.
    build_rag : bool
        If True, create/refresh the RAG index after predicates complete.
    run_predicates : bool
        If True, execute predicate runner to generate evidence.
    vendor : str
        Optional vendor name passed through to the predicate runner.
    version : str
        Optional vendor version passed through to the predicate runner.

    Returns
    -------
    RunResult
        Manifest with key artifact paths for downstream linking/inspection.

    Notes
    -----
    - Raises RuntimeError if predicates emit no evidence (fast fail).
    - Safe to call multiple times with the same `model_id` (idempotent layout).
    - Some artifacts may be None if a step was skipped (e.g., RAG disabled).
    """
    # PRE (model-scoped wipe, preserves model.xml)
    pre_run_cleanup(model_id)

    # Ensure the standard per-model directory layout exists (e.g., evidence/, parquet/).
    model_dir = paths.ensure_model_dirs(model_id)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Ingest XML → per-model DuckDB (optionally overwrite existing artifacts).
    if xml_path is not None:
        cmd = [
            sys.executable,
            "-m",
            "app.flow.ingest.loader_duckdb",
            "--xml",
            str(xml_path),
            "--model-id",
            model_id,
        ]
        if overwrite:
            cmd.append("--overwrite")
        _run(cmd)

    # Step 2: Build IR from the ingested tables.
    _run(
        [
            sys.executable,
            "-m",
            "app.flow.ingest.build_ir",
            "--model-dir",
            str(model_dir),
        ]
    )

    # Step 3: Run deterministic predicates (produces evidence.jsonl and optional summary).
    if run_predicates:
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "app.knowledge.criteria.runner",
            "--model-dir",
            str(model_dir),
        ]
        if vendor:
            cmd += ["--vendor", vendor]
        if version:
            cmd += ["--version", version]
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
            sj.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # non-fatal

    # Step 4: Build per-model RAG index (rag.sqlite) next to evidence.
    rag_db = None
    if build_rag:
        _run(
            [sys.executable, "-m", "app.artifacts.rag.build_index", str(ej)],
            cwd=model_dir,
        )
        rag_db = paths.rag_sqlite(model_id)

    # Return paths to key artifacts so callers (API/tests) can link or inspect.
    artifacts = {
        "xml": str(xml_path) if xml_path else None,
        "duckdb": str(paths.duckdb_path(model_id)),
        "evidence_jsonl": str(ej),
        "rag_sqlite": str(rag_db) if rag_db else None,
        "model_dir": str(model_dir),
    }

    # POST (snapshot + prune)
    post_run_cleanup(model_id)
    return RunResult(model_id=model_id, model_dir=model_dir, artifacts=artifacts)
