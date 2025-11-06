# app/core/config.py
from __future__ import annotations
from pathlib import Path
from typing import Literal, Union, Optional
from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env regardless of CWD
_ENV_FILE = (Path(__file__).resolve().parents[1] / ".env").as_posix()

# Central, typed configuration loaded from env + .env.
# Import `settings` from this module everywhere instead of re-reading env.
class Settings(BaseSettings):
    # Env wiring:
    # - env_file points at backend/.env (absolute) so CWD never matters.
    # - env_prefix=MBSE_ prevents accidental key collisions.
    # - extra="forbid" catches unknown env keys early (fail-fast).
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,          # ← absolute path to backend/.env
        env_prefix="MBSE_",          # ← avoid stray env keys; reads MBSE_DEFAULT_XML, etc.
        extra="forbid",
        case_sensitive=False,
    )
    
    # Anchor for resolving other paths; prefer deriving from this over using CWD.
    BACKEND_ROOT: Path = Path(__file__).resolve().parents[1]

    # Absolute locations for the RAG SQLite DB and schema; avoids per-process CWD drift.
    RAG_DB: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "app" / "rag" / "rag.sqlite"
    )
    
    # SQL schema file used to (re)initialize the RAG DB.
    SCHEMA_SQL: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "app" / "rag" / "schema.sql"
    )

    # Dev helper: fallback XML to load when none is supplied.
    # Alias preserves older env names without breaking callers.
    default_xml: Optional[Path] = Field(default=None, alias="DEFAULT_XML")

    # App toggles:
    # - APP_ENV gates dev-only behavior.
    # - LOG_LEVEL applies to both app and uvicorn (aligned in app.main).
    # - CORS_ORIGINS should be strict in prod (no "*" with credentials).
    APP_ENV: Literal["dev", "prod"] = "dev"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    ACCESS_LOG: bool = True
    MUTE_ALL_LOGS: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_UPLOAD_MB: int = 200
    
    # When True, mounts internal/debug routers (expose file paths, raw evidence).
    # Keep False in production.
    EXPOSE_INTERNALS: bool = False


    # Generation model name as understood by the provider (Ollama/OpenAI adapters map this).
    GEN_MODEL: str = "llama3.2:1b"
    OLLAMA: str = "ollama"  # "ollama" (CLI) or "http://localhost:11434" (HTTP)
    EMB_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Retrieval knobs; tune per model size to balance recall vs context packing.
    RAG_TOP_K: int = 12
    RAG_BM25_ONLY: bool = False
    RAG_MAX_CARD_CHARS: int = 600
    DEFAULT_MODEL_ID: str = "14b92d4a"
    
    # Sampling and context controls; validated ranges avoid provider-side 400s.
    # Mapped into `ollama_options` below (also used to normalize OpenAI configs).
    LLM_TEMP: float = Field(0.2, ge=0.0, le=1.0, description="Sampling temperature")
    LLM_TOP_P: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling")
    LLM_TOP_K: int = Field(40, ge=0, description="Top-K sampling (Ollama)")
    LLM_MAX_TOKENS: int = Field(512, ge=16, le=8192, description="Max new tokens / num_predict")
    LLM_NUM_CTX: int = Field(4096, ge=512, le=32768, description="Context window for Ollama models")
    LLM_REPEAT_PENALTY: float = Field(1.1, ge=0.0, le=2.0, description="Discourage repetition (Ollama)")
    LLM_SEED: Optional[int] = Field(None, description="Deterministic generations if supported")
    LLM_PROVIDER: Literal["ollama", "openai"] = "ollama"  # lets us switch later

    # Accept comma-separated string or list for CORS_ORIGINS; normalize to list[str].
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _coerce_origins(cls, v: Union[str, list[str]]):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Convert incoming env values to Path objects (supports strings like "~/.x").
    @field_validator("RAG_DB", "SCHEMA_SQL", "default_xml", mode="before")
    @classmethod
    def _coerce_path(cls, v: Union[str, Path] | None):
        if v is None:
            return None
        return v if isinstance(v, Path) else Path(v).expanduser()

    # Resolve to absolute Paths; existence is NOT checked here (creation is handled elsewhere).
    @field_validator("RAG_DB", "SCHEMA_SQL", "default_xml", mode="after")
    @classmethod
    def _abs_path(cls, v: Path | None):
        return None if v is None else v.resolve()

    # Provider options derived from validated fields.
    # Ensures numeric types and names match Ollama /api/generate payload.
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
