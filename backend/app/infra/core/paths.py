# ------------------------------------------------------------
# Module: app/infra/core/paths.py
# Purpose: Canonical, CWD-agnostic path helpers and repository roots.
# ------------------------------------------------------------

"""Centralized path management utilities.

Responsibilities
----------------
- Provide canonical, CWD-independent paths for all app components.
- Define reproducible directory roots shared by API, workers, and tests.
- Ensure per-model directories (e.g., evidence, parquet) are created idempotently.
- Offer consistent interfaces for resolving both local and packaged resources.
"""

from __future__ import annotations

import shutil
from importlib.resources import files as _pkg_files
from pathlib import Path
from uuid import uuid4

# ---- Fixed Roots (CWD-independent) ----
# Resolve once from this file’s location to guarantee consistent paths.
# paths.py now lives at app/infra/core/paths.py:
#   parents[0] = .../core
#   parents[1] = .../infra
#   parents[2] = .../app
#   parents[3] = .../backend
BACKEND_ROOT: Path = Path(__file__).resolve().parents[3]  # .../backend
APP_ROOT: Path = BACKEND_ROOT / "app"

#  runtime artifacts live under ops/data
OPS_ROOT: Path = BACKEND_ROOT / "ops"
DATA_DIR: Path = OPS_ROOT / "data"
MODELS_DIR: Path = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DB: Path = (DATA_DIR / "jobs.sqlite").resolve()

# RAG resources live under app/artifacts/rag
RAG_DIR: Path = APP_ROOT / "artifacts" / "rag"

# Temporary persistent storage for model artifacts
PERSISTENT_MODELS_ROOT: Path = (OPS_ROOT / "persistent").resolve()


# ---- Repository Paths ----
def repo_path(p: str | Path) -> Path:
    """Return an absolute path rooted at the repository backend.

    Notes
    -----
    - If `p` is already absolute, it is resolved and returned unchanged.
    - Otherwise, it is joined to BACKEND_ROOT and resolved.
    """
    p = Path(p)
    return p.resolve() if p.is_absolute() else (BACKEND_ROOT / p).resolve()


# ---- Per-Model Paths ----
def model_dir(model_id: str) -> Path:
    """Return the base directory for a given model (…/data/models/<id>)."""
    return (MODELS_DIR / model_id).resolve()


def xml_path(model_id: str) -> Path:
    """Return the path to `model.xml` for a given model."""
    return (model_dir(model_id) / "model.xml").resolve()


def duckdb_path(model_id: str) -> Path:
    """Return the path to `model.duckdb` for a given model."""
    return (model_dir(model_id) / "model.duckdb").resolve()


def parquet_dir(model_id: str) -> Path:
    """Return the directory used for per-model parquet files."""
    return (model_dir(model_id) / "parquet").resolve()


def evidence_dir(model_id: str) -> Path:
    """Return the directory used for evidence artifacts for a given model."""
    return (model_dir(model_id) / "evidence").resolve()


def evidence_jsonl(model_id: str) -> Path:
    """Return the path to `evidence.jsonl` inside a model’s evidence directory."""
    return (evidence_dir(model_id) / "evidence.jsonl").resolve()


def rag_sqlite(model_id: str) -> Path:
    """Return the path to a model’s `rag.sqlite` database."""
    return (model_dir(model_id) / "rag.sqlite").resolve()


def summary_json(model_id: str) -> Path:
    """Return the path to a model’s `summary.json` file."""
    return (model_dir(model_id) / "summary.json").resolve()


def ensure_model_dirs(model_id: str) -> Path:
    """Create (if missing) the standard per-model directory layout.

    Notes
    -----
    - Idempotent (safe to call more than once).
    - Ensures `<model>/`, `<model>/evidence/`, and `<model>/parquet/` exist.
    """
    mdir = model_dir(model_id)
    mdir.mkdir(parents=True, exist_ok=True)
    evidence_dir(model_id).mkdir(parents=True, exist_ok=True)
    parquet_dir(model_id).mkdir(parents=True, exist_ok=True)
    return mdir


# ---- Package Resources ----
def schema_sql_text() -> str:
    """Load `schema.sql` from package resources; fall back to local copy in dev.

    Notes
    -----
    - Returns the file contents as UTF-8 text.
    - Fallback path is `app/artifacts/rag/schema.sql` within the repo during development.
    """
    try:
        return (_pkg_files("app.artifacts.rag") / "schema.sql").read_text(
            encoding="utf-8"
        )
    except Exception:
        return (RAG_DIR / "schema.sql").read_text(encoding="utf-8")


# ---- Diagnostics ----
def log_path_map() -> dict[str, str]:
    """Return a snapshot of canonical paths for startup logs and diagnostics.

    Notes
    -----
    - All values are stringified absolute paths where applicable.
    - Useful for verifying environment/layout at boot.
    """
    return {
        "BACKEND_ROOT": str(BACKEND_ROOT),
        "APP_ROOT": str(APP_ROOT),
        "OPS_ROOT": str(OPS_ROOT),
        "DATA_DIR": str(DATA_DIR),
        "MODELS_DIR": str(MODELS_DIR),
        "RAG_DIR": str(RAG_DIR),
        "JOBS_DB": str(JOBS_DB),
        "PERSISTENT_MODELS_ROOT": str(PERSISTENT_MODELS_ROOT),
        "schema.sql (pkg)": "app/artifacts/rag/schema.sql",
    }


# ---- Snapshot helper (no deletion) ----
def snapshot_evidence(model_id: str) -> Path | None:
    """
    Copy per-model artifacts to: ops/persistent/<model_id>/
    - evidence/evidence.jsonl     → persistent/<id>/evidence.jsonl
    - summary.json                → persistent/<id>/summary.json
    - summary.api.json            → persistent/<id>/summary.api.json

    Returns the destination path for evidence.jsonl (historical behavior),
    or None if evidence was missing. Summaries are best-effort: if present,
    they are snapshotted atomically too.
    """
    src_model_dir = model_dir(model_id)
    src_ev_dir = evidence_dir(model_id)

    ev_src = src_ev_dir / "evidence.jsonl"
    sum_src = src_model_dir / "summary.json"
    sum_api_src = src_model_dir / "summary.api.json"

    dest_dir = (PERSISTENT_MODELS_ROOT / model_id).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_copy(src: Path, dest_name: str) -> Path | None:
        if not (src.exists() and src.is_file()):
            return None
        dest = dest_dir / dest_name
        tmp = dest_dir / f".{dest_name}.{uuid4().hex}.tmp"
        try:
            shutil.copy2(src, tmp)
            tmp.replace(dest)  # atomic on same filesystem
            return dest
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    # Preserve legacy return value (evidence path or None).
    ev_dest = _atomic_copy(ev_src, "evidence.jsonl")

    # Best-effort snapshot of summaries (don’t affect return semantics).
    _atomic_copy(sum_src, "summary.json")
    _atomic_copy(sum_api_src, "summary.api.json")

    return ev_dest


def wipe_ops_data() -> bool:
    """Remove the entire ops/data directory (including jobs.sqlite)."""
    removed = DATA_DIR.exists()
    if removed:
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return removed


def wipe_model_runtime(model_id: str) -> dict:
    """
    Remove per-model runtime artifacts while preserving model.xml.
    Deletes: jsonl/, parquet/, rag.sqlite, model.duckdb, evidence/* (but keeps dir)
    """
    m = model_dir(model_id)
    kept, removed = [], []

    # Preserve model.xml if present
    x = m / "model.xml"
    if x.exists():
        kept.append(str(x))

    # Nuke jsonl/parquet dirs (if present)
    for d in ("jsonl", "parquet"):
        p = m / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(str(p))
        (m / d).mkdir(parents=True, exist_ok=True)  # recreate empty for pipeline

    # Remove files we can rebuild
    for f in ("rag.sqlite", "model.duckdb"):
        p = m / f
        if p.exists():
            p.unlink(missing_ok=True)
            removed.append(str(p))

    # Clean evidence contents but keep the dir (fresh evidence will be written)
    ev = evidence_dir(model_id)
    if ev.exists():
        for child in ev.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink()
                    removed.append(str(child))
                elif child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    removed.append(str(child))
            except Exception:
                pass
    ev.mkdir(parents=True, exist_ok=True)

    return {"kept": kept, "removed": removed}


def prune_model_runtime(model_id: str) -> dict:
    """
    After the run, keep: evidence/evidence.jsonl, summary.json, rag.sqlite,
    and model.duckdb (so /v1/models works). Remove jsonl/, parquet/, etc.
    """
    m = model_dir(model_id)
    keep = {
        (evidence_dir(model_id) / "evidence.jsonl").resolve(),
        (m / "summary.json").resolve(),
        (m / "rag.sqlite").resolve(),
        (m / "summary.api.json").resolve(),
        (m / "model.duckdb").resolve(),
    }
    kept, removed = [], []

    # Drop jsonl/parquet entirely
    for d in ("jsonl", "parquet"):
        p = m / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed.append(str(p))

    # Remove any other stray files/dirs not in keep
    for child in m.iterdir():
        if child in keep or child.name in (
            "evidence",
            "summary.json",
            "rag.sqlite",
            "model.xml",
        ):
            continue
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
                removed.append(str(child))
            elif child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                removed.append(str(child))
        except Exception:
            pass

    # Record kept
    for p in keep:
        if p.exists():
            kept.append(str(p))
    return {"kept": kept, "removed": removed}
