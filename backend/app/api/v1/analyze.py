# ------------------------------------------------------------
# Module: app/api/v1/analyze.py
# Purpose: Implement model analysis endpoints for the MBSE Maturity backend.
# ------------------------------------------------------------

"""Model analysis endpoints for the MBSE Maturity backend.

Summary:
    Implements the API endpoints that accept MBSE models (XML uploads or JSON payloads),
    convert them into an internal temporary database, run maturity predicates,
    and return structured maturity scores plus evidence.

Details:
    - `/v1/analyze` accepts JSON payloads directly.
    - `/v1/analyze/upload` accepts multipart form-data with a model file.
    - Each request uses an input adapter (e.g., Sparx, Cameo) to parse the model XML
      into a temporary SQLite database for predicate-based evaluation.
    - The predicate engine runs deterministic checks to compute maturity level
      and evidence used in later RAG/LLM summarization.

Developer Guidance:
    - Use `/analyze` for internal testing and `/analyze/upload` for frontend integration.
    - Keep routes thin: handle validation, call service functions, log results.
    - All XML and database logic must stay within adapters or predicate modules.
    - Never persist uploaded models; keep analysis transient for security.
    - Log timing and vendor metadata for traceability.
    - When adding new vendors, register their adapters in `app/input_adapters/router.py`.
"""


from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from .models import AnalyzeRequest, AnalyzeResponse, Vendor
from app.input_adapters.router import get_adapter
from app.criteria.runner import run_predicates
from app.criteria.protocols import Context
import logging
import time

# -----------------------------------------------------------------------------
# Router setup
# -----------------------------------------------------------------------------
router: APIRouter = APIRouter()
log = logging.getLogger("maturity.api.analyze")

# Maximum accepted model upload size (in megabytes)
MAX_UPLOAD_MB = 50


@router.post("", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze an MBSE model from a JSON payload.

    Args:
        req (AnalyzeRequest): Parsed request containing vendor, version,
            model ID, and XML model bytes (Base64-decoded).

    Returns:
        AnalyzeResponse: Computed maturity level and evidence summary.

    Raises:
        HTTPException:
            - 400: Invalid vendor or adapter.
            - 500: Any unexpected internal failure.

    Workflow:
        1. Load vendor-specific adapter.
        2. Build a temporary in-memory SQLite DB from the model XML.
        3. Create analysis context (vendor, version, model_id).
        4. Run maturity predicates against the DB.
        5. Return structured maturity results.

    Logging:
        - Total timing (t0 → end)
        - Predicate runtime (tp → completion)
        - Vendor, version, and model_id for traceability.
    """
    t0 = time.perf_counter()
    db = None
    try:
        adapter = get_adapter(req.vendor.value, req.version)
        db = adapter.build_db(req.xml_bytes)  # Converts XML into in-memory SQLite
        ctx = Context(vendor=req.vendor.value, version=req.version, model_id=req.model_id)

        tp = time.perf_counter()
        level, evidence = run_predicates(db, ctx)
        log.info("timing predicates=%.1fms", (time.perf_counter() - tp) * 1000)

        res = AnalyzeResponse(maturity_level=level, evidence=evidence)
        log.info(
            "success model_id=%s vendor=%s version=%s duration_ms=%.1f",
            req.model_id, req.vendor.value, req.version, (time.perf_counter() - t0) * 1000,
        )
        return res

    except ValueError as e:
        # Handle known validation failures from adapter or input
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        # Log unexpected exceptions for triage
        log.exception("analysis_failed model_id=%s", req.model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
    finally:
        # Always close DB connection to avoid memory leaks
        if db is not None:
            try:
                db.close()
            except Exception:
                log.warning("db_close_failed", exc_info=True)


@router.post("/upload", response_model=AnalyzeResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    vendor: Vendor = Form(...),
    version: str = Form(...),
    model_id: str | None = Form(None),
) -> AnalyzeResponse:
    """Analyze an uploaded MBSE model file via multipart form-data.

    Args:
        file (UploadFile): The uploaded XML model file.
        vendor (Vendor): Model source (e.g., Sparx, Cameo).
        version (str): Vendor version (e.g., "17.1").
        model_id (str | None): Optional unique identifier for traceability.

    Returns:
        AnalyzeResponse: Computed maturity level and evidence details.

    Raises:
        HTTPException:
            - 413: File too large.
            - 400/500: See `analyze()` handler.

    Example:
        curl -F "file=@model.xml" -F "vendor=sparx" -F "version=17.1" \\
             http://127.0.0.1:8000/v1/analyze/upload

    Notes:
        - File is read entirely into memory for simplicity.
        - Maximum upload size enforced by `MAX_UPLOAD_MB`.
        - Reuses the same analysis flow as the JSON route.
    """
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")

    req = AnalyzeRequest(model_id=model_id, vendor=vendor, version=version, xml_bytes=data)
    return analyze(req)