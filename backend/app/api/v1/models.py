# ------------------------------------------------------------
# Module: app/api/v1/models.py
# Purpose: Define request and response models for maturity analysis.
# ------------------------------------------------------------

"""Pydantic models shared by the analysis API endpoints.

Summary:
    Defines validated data structures used by both `/v1/analyze` JSON and
    multipart endpoints. Handles base64 decoding for XML uploads and ensures
    consistent typing for backend logic.

Developer Guidance:
    - Keep these models minimal and serialization-safe.
    - Avoid importing business logic here; this layer defines I/O contracts only.
    - Extend with new fields *only* after updating all dependent routes and tests.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, field_validator
import base64


class Vendor(str, Enum):
    """Supported MBSE modeling tool vendors.

    Attributes:
        sparx (str): Represents Sparx Enterprise Architect exports.
        cameo (str): Represents Cameo Systems Modeler exports.

    Developer Guidance:
        Use `Vendor` to ensure vendor-specific parsing logic stays explicit.
        Do not compare vendor strings manually—use the Enum members.
    """

    sparx = "sparx"
    cameo = "cameo"


class AnalyzeRequest(BaseModel):
    """Incoming request model for `/v1/analyze`.

    Attributes:
        model_id (str | None): Optional identifier for the uploaded model.
        vendor (Vendor): The MBSE tool type ("sparx" or "cameo").
        version (str): Tool version string (e.g., "17.1").
        xml_bytes (bytes): Raw XML content as bytes or base64-encoded string.

    Developer Guidance:
        - Keep validation lightweight; heavy parsing occurs downstream.
        - For multipart uploads, FastAPI handles binary bytes automatically.
        - For JSON uploads, XML content must be base64-encoded.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: str | None = None
    vendor: Vendor
    version: str
    xml_bytes: bytes  # JSON: base64 string → bytes; multipart: bytes

    @field_validator("xml_bytes", mode="before")
    @classmethod
    def _b64_to_bytes(cls, v: Any) -> bytes:
        """Decode a base64-encoded XML payload when received via JSON.

        Args:
            v (Any): Raw input value (may be bytes, bytearray, or base64 string).

        Returns:
            bytes: Decoded XML bytes ready for in-memory processing.

        Raises:
            ValueError: If the string cannot be base64-decoded.
            TypeError: If the input type is unsupported.

        Developer Guidance:
            This conversion allows consistent handling between JSON and multipart
            upload routes. Avoid performing any XML parsing here.
        """
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, str):
            try:
                return base64.b64decode(v, validate=True)
            except Exception as e:
                raise ValueError("xml_bytes must be base64-encoded") from e
        raise TypeError("xml_bytes must be bytes or base64 string")


class EvidenceItem(BaseModel):
    """Single maturity criterion result.

    Attributes:
        predicate (str): Name of the evaluated maturity predicate.
        passed (bool): True if the predicate condition succeeded.
        details (dict[str, Any]): Optional context or diagnostic data.

    Developer Guidance:
        - Keep `details` JSON-serializable.
        - Use concise, human-readable keys for clarity in the frontend.
        - Avoid nesting deeply; this is meant for summaries, not full traces.
    """

    model_config = ConfigDict(extra="forbid")

    predicate: str
    passed: bool
    details: dict[str, Any] = {}


class AnalyzeResponse(BaseModel):
    """Response model for `/v1/analyze` results.

    Attributes:
        maturity_level (int): Highest verified MML level achieved.
        evidence (list[EvidenceItem]): Predicate results per maturity check.

    Developer Guidance:
        - Always include all predicates evaluated, even if failed.
        - The frontend uses this to visualize maturity progress.
        - Do not perform post-processing here—serialize directly.
    """

    model_config = ConfigDict(extra="forbid")

    maturity_level: int
    evidence: list[EvidenceItem] = []
