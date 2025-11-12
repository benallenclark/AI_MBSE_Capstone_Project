# ------------------------------------------------------------
# Module: app/core/paths.py
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

from importlib.resources import files as _pkg_files
from pathlib import Path

# ---- Fixed Roots (CWD-independent) ----
# Resolves once from this file’s location to guarantee consistent paths.
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]  # .../backend
APP_ROOT: Path = BACKEND_ROOT / "app"
DATA_DIR: Path = BACKEND_ROOT / "data"
MODELS_DIR: Path = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
RAG_DIR: Path = APP_ROOT / "rag"
JOBS_DB: Path = (DATA_DIR / "jobs.sqlite").resolve()


# ---- Repository Paths ----
def repo_path(p: str | Path) -> Path:
    p = Path(p)
    return p.resolve() if p.is_absolute() else (BACKEND_ROOT / p).resolve()


# ---- Per-Model Paths ----
def model_dir(model_id: str) -> Path:
    """Base directory for a given model."""
    return (MODELS_DIR / model_id).resolve()


def xml_path(model_id: str) -> Path:
    """Path to model.xml for a given model."""
    return (model_dir(model_id) / "model.xml").resolve()


def duckdb_path(model_id: str) -> Path:
    """Path to model.duckdb for a given model."""
    return (model_dir(model_id) / "model.duckdb").resolve()


def parquet_dir(model_id: str) -> Path:
    """Directory for per-model parquet files."""
    return (model_dir(model_id) / "parquet").resolve()


def evidence_dir(model_id: str) -> Path:
    """Directory for evidence artifacts for a given model."""
    return (model_dir(model_id) / "evidence").resolve()


def evidence_jsonl(model_id: str) -> Path:
    """Path to evidence.jsonl under a model’s evidence directory."""
    return (evidence_dir(model_id) / "evidence.jsonl").resolve()


def rag_sqlite(model_id: str) -> Path:
    """Path to a model’s rag.sqlite database."""
    return (model_dir(model_id) / "rag.sqlite").resolve()


def summary_json(model_id: str) -> Path:
    """Path to a model’s summary.json file."""
    return (model_dir(model_id) / "summary.json").resolve()


def ensure_model_dirs(model_id: str) -> Path:
    """Create the standard per-model directory layout"""
    mdir = model_dir(model_id)
    mdir.mkdir(parents=True, exist_ok=True)
    evidence_dir(model_id).mkdir(parents=True, exist_ok=True)
    parquet_dir(model_id).mkdir(parents=True, exist_ok=True)
    return mdir


# ---- Package Resources ----
def schema_sql_text() -> str:
    """Load schema.sql from package resources, fallback to local copy during development."""
    try:
        return (_pkg_files("app.rag") / "schema.sql").read_text(encoding="utf-8")
    except Exception:
        return (RAG_DIR / "schema.sql").read_text(encoding="utf-8")


# ---- Diagnostics ----
def log_path_map() -> dict[str, str]:
    """Return canonical paths snapshot for startup logging and diagnostics."""
    return {
        "BACKEND_ROOT": str(BACKEND_ROOT),
        "APP_ROOT": str(APP_ROOT),
        "DATA_DIR": str(DATA_DIR),
        "MODELS_DIR": str(MODELS_DIR),
        "RAG_DIR": str(RAG_DIR),
        "JOBS_DB": str(JOBS_DB),
        "schema.sql (pkg)": "app/rag/schema.sql",
    }
