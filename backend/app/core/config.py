# ------------------------------------------------------------
# Module: app/core/config.py
# Purpose: Central, typed application settings loaded from env + backend/.env.
# ------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env regardless of CWD
_ENV_FILE = (Path(__file__).resolve().parents[1] / ".env").as_posix()


# Single source of truth for configuration.
# Import `settings` from this module instead of re-instantiating Settings().
class Settings(BaseSettings):
    # Env model: absolute env_file, namespaced keys, forbid extras
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,  # absolute path so CWD never matters
        env_prefix="MBSE_",  # avoid collisions; e.g., MBSE_DEFAULT_XML
        extra="forbid",  # catch unknown keys early
        case_sensitive=False,
    )

    # Anchor path for deriving other locations (prefer over CWD assumptions)
    BACKEND_ROOT: Path = Path(__file__).resolve().parents[1]

    # SQL schema for initializing the RAG DB.
    SCHEMA_SQL: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1]
        / "app"
        / "rag"
        / "schema.sql"
    )

    # Base directory under which each per-model RAG DB lives.
    # Example: backend/data/models/<model_id>/rag.sqlite
    MODELS_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "data" / "models"
    )

    # Dev helper: fallback XML to load when none is supplied.
    # Alias preserves older env names without breaking callers.
    default_xml: Path | None = Field(default=None, alias="DEFAULT_XML")

    # App toggles
    APP_ENV: Literal["dev", "prod"] = "dev"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    ACCESS_LOG: bool = True
    MUTE_ALL_LOGS: bool = False
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]
    MAX_UPLOAD_MB: int = 200

    # Internal/debug exposure (keep False in prod)
    EXPOSE_INTERNALS: bool = False

    # Model/provider knobs
    GEN_MODEL: str = "llama3.2:1b"
    OLLAMA: str = "ollama"  # "ollama" (CLI) or "http://localhost:11434" (HTTP)
    EMB_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Retrieval tuning
    RAG_TOP_K: int = 12
    RAG_BM25_ONLY: bool = False
    RAG_MAX_CARD_CHARS: int = 600
    DEFAULT_MODEL_ID: str = "14b92d4a"

    # ---- DuckDB resource knobs (used by app.ingest.session / loader) ----
    # Environment variables respected via existing prefix:
    #   MBSE_DUCKDB_THREADS=4
    #   MBSE_DUCKDB_MEM=1GB
    DUCKDB_THREADS: int = Field(4, ge=1, description="DuckDB PRAGMA threads")
    DUCKDB_MEM: str = Field("1GB", description="DuckDB PRAGMA memory_limit")

    # ---- LLM sampling/context controls (validated to avoid provider 400s) ----
    LLM_TEMP: float = Field(0.2, ge=0.0, le=1.0, description="Sampling temperature")
    LLM_TOP_P: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling")
    LLM_TOP_K: int = Field(40, ge=0, description="Top-K sampling (Ollama)")
    LLM_MAX_TOKENS: int = Field(
        512, ge=16, le=8192, description="Max new tokens / num_predict"
    )
    LLM_NUM_CTX: int = Field(
        4096, ge=512, le=32768, description="Context window for Ollama models"
    )
    LLM_REPEAT_PENALTY: float = Field(
        1.1, ge=0.0, le=2.0, description="Discourage repetition (Ollama)"
    )
    LLM_SEED: int | None = Field(
        None, description="Deterministic generations if supported"
    )
    LLM_PROVIDER: Literal["ollama", "openai"] = "ollama"  # lets us switch later

    # Accept comma-separated string or list for CORS_ORIGINS; normalize to list[str].
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _coerce_origins(cls, v: str | list[str]):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Convert incoming env values to Path objects (supports strings like "~/.x").
    @field_validator("SCHEMA_SQL", "default_xml", "MODELS_DIR", mode="before")
    @classmethod
    def _coerce_path(cls, v: str | Path | None):
        if v is None:
            return None
        return v if isinstance(v, Path) else Path(v).expanduser()

    # Resolve to absolute Paths; existence is validated elsewhere.
    @field_validator("SCHEMA_SQL", "default_xml", "MODELS_DIR", mode="after")
    @classmethod
    def _abs_path(cls, v: Path | None):
        return None if v is None else v.resolve()

    # Provider options derived from validated fields (Ollama /api/generate)
    @computed_field(return_type=dict)
    def ollama_options(self) -> dict:
        """Options map for Ollama /api/generate."""
        opts = {
            "temperature": self.LLM_TEMP,
            "top_p": self.LLM_TOP_P,
            "top_k": self.LLM_TOP_K,
            "num_predict": self.LLM_MAX_TOKENS,
            "num_ctx": self.LLM_NUM_CTX,
            "repeat_penalty": self.LLM_REPEAT_PENALTY,
        }
        if self.LLM_SEED is not None:
            opts["seed"] = self.LLM_SEED
        return opts


# Eagerly instantiate once at import; Pydantic caches env reads.
# Import `settings` anywhere; do not re-create Settings().
settings = Settings()
