# ------------------------------------------------------------
# Module: app/api/v1/models.py
# Purpose: Public request/response contracts for the analysis API.
# ------------------------------------------------------------

"""Typed contracts for the MBSE Maturity API.
Defines enums and Pydantic models for requests, evidence rows, predicate
results, analysis responses, and job status payloads.

Responsibilities
----------------
- Specify strict request/response schemas for /v1 endpoints.
- Enforce validation (e.g., base64 decoding, object-shaped details).
- Provide stable wire types with explicit enums and defaults.
- Centralize job payload shapes for polling and navigation links.
"""

from __future__ import annotations

import base64
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Wire enum for supported model vendors; values are part of the public API..
class Vendor(str, Enum):
    """Supported MBSE vendors."""

    sparx = "sparx"
    cameo = "cameo"


# JSON request schema for synchronous /v1/analyze (non-multipart) uploads.
class AnalyzeRequest(BaseModel):
    """JSON request payload for /v1/analyze (non-multipart)."""

    # Reject unknown fields so clients can't send accidental/ignored data.
    model_config = ConfigDict(extra="forbid")

    model_id: str | None = None
    vendor: Vendor
    version: str

    # For JSON, xml_bytes must be base64;
    # the validator below decodes to raw bytes.
    xml_bytes: bytes

    # Decode base64 input into raw bytes for xml_bytes; fail fast on bad input.
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


# Internal evidence row used pre-API; details must be a JSON object.
class EvidenceItem(BaseModel):
    """Single maturity predicate result (internal representation)."""

    model_config = ConfigDict(extra="forbid")

    predicate: str
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    # Validate details to ensure an object (not a serialized JSON string).
    @field_validator("details", mode="before")
    @classmethod
    def _details_must_be_object(cls, v):
        if isinstance(v, str):
            raise ValueError("details must be an object, not a JSON string")
        return v


# Public-facing predicate result shape for UI consumption.
class PredicateResult(BaseModel):
    """Flattened, response-friendly predicate row."""

    id: str  # e.g., "mml_2:block_has_port"
    mml: int  # parsed from id
    passed: bool
    details: dict[str, Any]
    error: str | None = None


# Echo the model vendor/version back to clients (for caching and display).
class ModelEcho(BaseModel):
    """Vendor/version echo included in analysis responses."""

    model_config = ConfigDict(extra="forbid")
    vendor: str
    version: str


# Aggregate pass/fail/total counters for analysis summaries.
class SummaryCounts(BaseModel):
    """Pass/fail/total counts used by the UI and clients."""

    model_config = ConfigDict(extra="forbid")
    total: int
    passed: int
    failed: int


# Canonical analysis response for model summaries and (dev) sync analysis.
class AnalyzeContract(BaseModel):
    """Wire contract for GET /v1/models/{model_id} and dev POST /v1/analyze."""

    schema_version: str = "1.0"
    model: ModelEcho
    maturity_level: int
    summary: SummaryCounts
    results: list[PredicateResult]


# Hypermedia links associated with a job payload.
class JobLinks(BaseModel):
    """Canonical self/result links for job navigation."""

    model_config = ConfigDict(extra="forbid")
    self: str
    result: str


# Enumerated job states; values are wire-stable and public.
class JobStatus(str, Enum):
    """Allowed job lifecycle statuses for polling."""

    queued = "queued"
    running = "running"
    failed = "failed"
    succeeded = "succeeded"


# Canonical job status payload for upload + polling endpoints.
class JobContract(BaseModel):
    """Wire contract for POST /v1/analyze/upload and GET /v1/jobs/{job_id}."""

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
