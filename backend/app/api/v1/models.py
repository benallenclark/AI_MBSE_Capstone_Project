# ------------------------------------------------------------
# Module: app/api/v1/models.py
# Purpose: Public request/response contracts for the analysis API.
# ------------------------------------------------------------
from __future__ import annotations

import base64
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Wire enum (serialized as strings):
# - Values are part of the public API. Changing them is a breaking change.
class Vendor(str, Enum):
    """Supported MBSE vendors."""

    sparx = "sparx"
    cameo = "cameo"


# JSON request for /v1/analyze (non-multipart):
# - Use this model only for JSON uploads. Multipart uses UploadFile directly.
# - Enforce strict contract (extra="forbid") to avoid silent field drift.
class AnalyzeRequest(BaseModel):
    """JSON request payload for /v1/analyze (non-multipart).

    Note:
        - For multipart uploads, FastAPI gives bytes directly (no need for this model).
        - For JSON uploads, `xml_bytes` must be base64-encoded; we decode here.
    """

    # Reject unknown fields so clients can't send accidental/ignored data.
    model_config = ConfigDict(extra="forbid")

    model_id: str | None = None
    vendor: Vendor
    version: str

    # For JSON, xml_bytes must be base64;
    # the validator below decodes to raw bytes.
    xml_bytes: bytes

    # Accept bytes or base64 string; fail fast with clear errors on bad input.
    @field_validator("xml_bytes", mode="before")
    @classmethod
    def _b64_to_bytes(cls, v: Any) -> bytes:
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, str):
            try:
                return base64.b64decode(v, validate=True)
            except Exception as e:
                raise ValueError("xml_bytes must be base64-encoded") from e
        raise TypeError("xml_bytes must be bytes or base64 string")


# Internal evidence row (pre-API):
# - details must be a JSON object (not a string); keep it small & serializable.
class EvidenceItem(BaseModel):
    """Single maturity predicate result (used internally and summarized for responses)."""

    model_config = ConfigDict(extra="forbid")

    predicate: str
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    # Guard against dumping JSON strings into "details" by mistake.
    @field_validator("details", mode="before")
    @classmethod
    def _details_must_be_object(cls, v):
        if isinstance(v, str):
            raise ValueError("details must be an object, not a JSON string")
        return v


# Public predicate result:
# - id encodes rung + rule (e.g., "mml_2:block_has_port"); keep it stable.
# - mml parsed from id for quick UI grouping/filtering.
class PredicateResult(BaseModel):
    """Flattened, response-friendly predicate row."""

    id: str  # e.g., "mml_2:block_has_port"
    mml: int  # parsed from id
    passed: bool
    details: dict[str, Any]
    error: str | None = None


# ----------------------------- #
# Public analysis response (FINAL)
# ----------------------------- #
class ModelEcho(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendor: str
    version: str


class SummaryCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    passed: int
    failed: int


# Canonical analysis response:
# - schema_version guards wire compatibility; bump only on breaking changes.
# - "model" carries vendor/version echo for client caching and display.
class AnalyzeContract(BaseModel):
    """
    Canonical response for:
      - GET /v1/models/{model_id}
      - (optionally) POST /v1/analyze  (sync/dev)
    """

    schema_version: str = "1.0"
    model: ModelEcho
    maturity_level: int
    summary: SummaryCounts
    results: list[PredicateResult]


# ----------------------------- #
# Optional: unify job wire types
# ----------------------------- #
class JobLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    self: str
    result: str


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    failed = "failed"
    succeeded = "succeeded"


class JobContract(BaseModel):
    """
    Canonical job payload for:
      - POST /v1/analyze/upload (202)
      - GET  /v1/jobs/{job_id}
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str
    model_id: str
    status: JobStatus
    progress: int
    message: str = ""
    timings: dict[str, Any] | None = None
    links: JobLinks


__all__ = [
    "Vendor",
    "AnalyzeRequest",
    "EvidenceItem",
    "PredicateResult",
    "AnalyzeContract",
    "JobContract",
    "JobLinks",
    "JobStatus",
]
