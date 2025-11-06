# ------------------------------------------------------------
# Module: app/core/paths.py
# Purpose: Canonical, CWD-agnostic path helpers and roots.
# ------------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from importlib.resources import files as _pkg_files

# Resolve once from this file’s location so imports/workers/tests share identical paths.
# ---- Pin roots (these never depend on CWD) ----
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]   # .../backend
APP_ROOT: Path = BACKEND_ROOT / "app"
DATA_DIR: Path = BACKEND_ROOT / "data"
MODELS_DIR: Path = DATA_DIR / "models"
RAG_DIR: Path = APP_ROOT / "rag"
JOBS_DB: Path = (DATA_DIR / "jobs.sqlite").resolve()

# Resolve a path relative to BACKEND_ROOT when given a relative input.
# Use for config/files that are stored under the repo tree.
def repo_path(p: str | Path) -> Path:
    p = Path(p)
    return p.resolve() if p.is_absolute() else (BACKEND_ROOT / p).resolve()

# ---- Legacy/global (avoid in new code; prefer per-model) ----
# Backwards-compat: keep a global RAG DB path for older tools.
# New code should always prefer per-model rag.sqlite.
RAG_DB: Path = (RAG_DIR / "rag.sqlite").resolve()

# Canonical per-model layout; callers should build paths via these helpers.
def model_dir(model_id: str) -> Path:
    return (MODELS_DIR / model_id).resolve()

def xml_path(model_id: str) -> Path:
    return (model_dir(model_id) / "model.xml").resolve()

def duckdb_path(model_id: str) -> Path:
    return (model_dir(model_id) / "model.duckdb").resolve()

def parquet_dir(model_id: str) -> Path:
    return (model_dir(model_id) / "parquet").resolve()

def evidence_dir(model_id: str) -> Path:
    return (model_dir(model_id) / "evidence").resolve()

def evidence_jsonl(model_id: str) -> Path:
    return (evidence_dir(model_id) / "evidence.jsonl").resolve()

def rag_sqlite(model_id: str) -> Path:
    return (model_dir(model_id) / "rag.sqlite").resolve()

def summary_json(model_id: str) -> Path:
    return (model_dir(model_id) / "summary.json").resolve()

# Create the standard per-model structure idempotently (model/, evidence/, parquet/).
# Safe to call on every run.
def ensure_model_dirs(model_id: str) -> Path:
    """Create the standard per-model folders up front."""
    mdir = model_dir(model_id)
    mdir.mkdir(parents=True, exist_ok=True)
    evidence_dir(model_id).mkdir(parents=True, exist_ok=True)
    parquet_dir(model_id).mkdir(parents=True, exist_ok=True)
    return mdir

# ---- Read-only resource (schema.sql) ----
# Load schema.sql from the installed package; fall back to repo copy during dev.
def schema_sql_text() -> str:
    try:
        return (_pkg_files("app.rag") / "schema.sql").read_text(encoding="utf-8")
    except Exception:
        return (RAG_DIR / "schema.sql").read_text(encoding="utf-8")

# Snapshot of canonical paths for startup logs and diagnostics.
def log_path_map() -> dict[str, str]:
    return {
        "BACKEND_ROOT": str(BACKEND_ROOT),
        "APP_ROOT": str(APP_ROOT),
        "DATA_DIR": str(DATA_DIR),
        "MODELS_DIR": str(MODELS_DIR),
        "RAG_DIR": str(RAG_DIR),
        "RAG_DB (legacy)": str(RAG_DB),
        "JOBS_DB": str(JOBS_DB),
        "schema.sql (pkg)": "app/rag/schema.sql",
    }
