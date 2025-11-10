# ------------------------------------------------------------
# Module: app/core/config.py
# Purpose: Centralize application configuration and environment management.
# ------------------------------------------------------------

"""Application configuration and environment management.

Summary:
    Centralizes all environment-driven configuration using Pydantic Settings.
    Ensures predictable runtime behavior between development and production
    by enforcing strict schema validation and typed defaults.

Details:
    - Reads environment variables (via `.env` or system environment).
    - Provides consistent configuration for logging, CORS, and environment flags.
    - Fails fast on unknown keys to avoid silent misconfiguration.
    - Converts comma-separated CORS origins into proper list form.

Developer Guidance:
    - Define all environment-dependent settings here—never hardcode in code.
    - Keep defaults minimal and safe for development.
    - Use `settings.APP_ENV` for environment-specific branching.
    - Add new fields with clear defaults and type annotations.
    - Validate sensitive configuration values before startup to prevent runtime errors.
"""

from typing import Literal, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# -----------------------------------------------------------------------------
# Configuration model
# -----------------------------------------------------------------------------
class Settings(BaseSettings):
    """Global environment configuration for the MBSE Maturity API.

    Attributes:
        APP_ENV (Literal["dev", "prod"]): Deployment environment mode.
        LOG_LEVEL (Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]): Global logging verbosity.
        ACCESS_LOG (bool): Enables or disables Uvicorn’s access logs.
        MUTE_ALL_LOGS (bool): If True, suppresses all log output.
        CORS_ORIGINS (list[str]): List of allowed origins for CORS middleware.

    Behavior:
        - Reads from `.env` file automatically.
        - Forbids unknown configuration keys (ensures schema compliance).
        - Coerces comma-separated string of origins into a list.
    """

    # Environment configuration
    APP_ENV: Literal["dev", "prod"] = "dev"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    ACCESS_LOG: bool = True  # Toggle uvicorn.access on/off
    MUTE_ALL_LOGS: bool = False

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]

    # Settings behavior
    model_config = SettingsConfigDict(
        env_file=".env",  # load environment from this file if present
        extra="forbid",   # fail on unknown env vars to ensure stability
    )

    # -----------------------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------------------
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _coerce_origins(cls, v: Union[str, list[str]]):
        """Normalize origins into a list, even if provided as comma-separated string.

        Example:
            "http://a.com,http://b.com" → ["http://a.com", "http://b.com"]
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# -----------------------------------------------------------------------------
# Singleton instance
# -----------------------------------------------------------------------------
# Instantiated once at import so misconfiguration fails early on startup.
settings = Settings()
