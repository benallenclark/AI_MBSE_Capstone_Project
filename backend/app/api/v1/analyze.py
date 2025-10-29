# ------------------------------------------------------------
# Module: app/api/v1/analyze.py
# Purpose: Implement model analysis endpoints for the MBSE Maturity backend.
# ------------------------------------------------------------

"""Analysis API endpoints (contract v1).

Summary:
    Accepts MBSE model XML via JSON or multipart, converts it into a temporary
    in-memory SQLite database through a vendor adapter, executes maturity
    predicates, and returns an AnalyzeContract response.

Key behaviors:
    - Determinism proof:
        • X-Model-SHA256: SHA256 of the raw XML bytes
        • X-Analysis-Fingerprint: SHA256 of normalized results (stable JSON)
      Identical inputs → identical fingerprints.
    - Performance:
        • Total analysis duration measured in milliseconds (float in logs,
          rounded int in the API contract).
        • Per-predicate timing is centralized in the predicate runner.
    - Safety & lifecycle:
        • No persistence to disk.
        • The SQLite connection is always closed in a 'finally' block.
        • Vendor logic is encapsulated in the adapter.

Developer notes:
    - Keep route logic thin; parsing/checks live in adapters and predicates.
    - 'results' is List[PredicateResult] (Pydantic), not list[dict].
    - When adding predicates, ensure 'details' is JSON-serializable and stable.
"""


from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from .models import AnalyzeRequest, Vendor, AnalyzeContract, EvidenceItem, PredicateResult
from app.input_adapters.router import get_adapter
from app.criteria.runner import run_predicates
from app.criteria.protocols import Context
from app.utils.timing import now_ns, ms_since
import logging
import hashlib, json

# Response models exclude None so optional fields (e.g., "error") are omitted.
router: APIRouter = APIRouter()
log = logging.getLogger("maturity.api.analyze")

# Maximum accepted model upload size (MiB). Prevents oversized payloads from being read into memory.
MAX_UPLOAD_MB = 100

@router.post("", response_model=AnalyzeContract, response_model_exclude_none=True)
def analyze(req: AnalyzeRequest, response: Response) -> AnalyzeContract:
    """Analyze a model provided as JSON and return an ``AnalyzeContract``.

    Args:
        req: Validated JSON request containing ``vendor``, ``version``,
            optional ``model_id``, and base64 ``xml_bytes``.
        response: FastAPI response object used to set audit headers.

    Returns:
        AnalyzeContract: Contract v1 payload with
            - ``model`` (vendor/version),
            - ``maturity_level`` (aggregate),
            - ``summary`` (``total``, ``passed``, ``failed``),
            - ``results`` (list of ``PredicateResult``).

    Raises:
        HTTPException: 400 on adapter/input validation errors; 500 on unexpected failures.

    Response Headers:
        X-Model-SHA256: SHA256 of input bytes.
        X-Analysis-Fingerprint: SHA256 of canonicalized results JSON.
    """
    
    # Delegate to the shared implementation (adds headers, timing, fingerprinting).
    return _analyze_impl(req, response)


@router.post("/upload", response_model=AnalyzeContract, response_model_exclude_none=True)
async def analyze_upload(
    response: Response,
    file: UploadFile = File(...),
    vendor: Vendor = Form(...),
    version: str = Form(...),
    model_id: str | None = Form(None),
) -> AnalyzeContract:
    """Analyze a model uploaded via multipart form-data.

    Args:
        response: FastAPI response object used to set audit headers.
        file: XML model file.
        vendor: Source system (e.g., ``"sparx"``, ``"cameo"``).
        version: Vendor version string (e.g., ``"17.1"``).
        model_id: Optional caller-supplied identifier for correlation.

    Returns:
        AnalyzeContract: Same shape as the JSON route.

    Raises:
        HTTPException:
            413 if the file exceeds ``MAX_UPLOAD_MB``.
            400/500 as per the JSON route.
    """

    data = await file.read()
    
    # Early reject to avoid processing oversized payloads.
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")

    req = AnalyzeRequest(model_id=model_id, vendor=vendor, version=version, xml_bytes=data)
    
    # Mirror the JSON route by constructing an AnalyzeRequest and delegating.
    return _analyze_impl(req, response)


# Derive a stable model identifier:
# - model_sha: SHA256 over raw XML bytes (proof of identical input).
# - model_id: caller-provided or first 8 chars of model_sha for correlation.

def _analyze_impl(req: AnalyzeRequest, response: Response) -> AnalyzeContract:
    """Core analysis pipeline.

    Steps:
        1) Compute ``model_sha`` (SHA256 of input bytes) and derive a stable ``model_id``.
        2) Build an in-memory SQLite DB via the vendor adapter.
        3) Time total analysis and execute predicates with context (vendor/version/model_id).
        4) Normalize evidence into ``PredicateResult`` models.
        5) Compute a canonical output fingerprint over results JSON.
        6) Log a single success line and set audit headers on the response.

    Args:
        req: Analyze request (already validated).
        response: FastAPI response to receive audit headers.

    Returns:
        AnalyzeContract: Fully-populated contract v1 payload.

    Raises:
        HTTPException: Translates adapter/input errors to 400; unexpected to 500.

    Side Effects:
        Sets ``X-Model-SHA256`` and ``X-Analysis-Fingerprint`` headers on the response.
    """

    model_sha = hashlib.sha256(req.xml_bytes).hexdigest()
    model_id = req.model_id or model_sha[:8]

    db = None
    try:
        # Parse and materialize the model:
        # - Adapter chosen by (vendor, version).
        # - Adapter returns an in-memory sqlite3.Connection.
        # - Adapter may raise ValueError for input/parse issues (mapped to HTTP 400).

        adapter = get_adapter(req.vendor.value, req.version)
        db = adapter.build_db(req.xml_bytes)

        # Measure total analysis duration in ms (float for logs, int for contract).
        # Per-predicate timing/logging is handled inside the predicate runner.
        t0 = now_ns()
        ctx = Context(vendor=req.vendor.value, version=req.version, model_id=model_id)
        level, evidence = run_predicates(db, ctx)

        total_ms_f = ms_since(t0)  # float ms for logs
        total_ms_int = int(round(total_ms_f))  # contract requires int

        results = _normalize_results(evidence)
        
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        
        # Deterministic output fingerprint:
        # - Sort results by (mml, id) to ensure stable order.
        # - Use model_dump(exclude_none=True) and compact JSON to avoid whitespace/key order variance.
        # - SHA256 over the canonical JSON proves deterministic output for a given input.

        fingerprint = hashlib.sha256(
            json.dumps(
                [r.model_dump(exclude_none=True) for r in sorted(results, key=lambda r: (r.mml, r.id))],
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        # Single success log:
        # - Includes model_id, vendor/version, xml_sha8, fp8, and total_ms (float displayed compactly).
        total_ms_str = f"{total_ms_f:.3f}" if total_ms_f < 1.0 else f"{int(round(total_ms_f))}"
        log.info(
            "success model_id=%s vendor=%s version=%s xml_sha8=%s fp8=%s total_ms=%s",
            model_id, req.vendor.value, req.version, model_sha[:8], fingerprint[:8], total_ms_str
        )

        # Expose determinism proof to clients for audit/regression:
        # - X-Model-SHA256: input hash
        # - X-Analysis-Fingerprint: output hash

        if response is not None:
            response.headers["X-Model-SHA256"] = model_sha
            response.headers["X-Analysis-Fingerprint"] = fingerprint

        return AnalyzeContract(
            model={"vendor": req.vendor.value, "version": req.version},
            maturity_level=level,
            summary={"total": len(results), "passed": passed, "failed": failed},
            results=results,
        )

    except ValueError as e:
        # Adapter/input validation errors become HTTP 400 with the original message.
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        # Unexpected failures become HTTP 500. Always log with model_id for correlation.
        log.exception("analysis_failed model_id=%s", model_id)
        raise HTTPException(status_code=500, detail="analysis_failed")
    finally:
        # Always close the temporary SQLite connection; logging of close failures is best-effort.
        if db is not None:
            try:
                db.close()
            except Exception:
                log.warning("db_close_failed", exc_info=True)


# Normalize internal EvidenceItem → PredicateResult models (typed, Pydantic).
# Keep 'details' pass-through and JSON-serializable. Do not mutate predicate data.
def _normalize_results(evidence: list[EvidenceItem]) -> list[PredicateResult]:
    """Convert internal evidence into contract-typed results.

    Args:
        evidence: Items with fields ``predicate`` (``"mml_x:predicate_id"``),
            ``passed`` (bool), ``details`` (dict), and optional ``error`` (str).

    Returns:
        list[PredicateResult]: Each item contains:
            - ``id``: ``"<group>:<predicate>"`` (e.g., ``"mml_2:block_has_port"``)
            - ``mml``: Parsed integer from group (defaults to 0 on parse failure)
            - ``passed``: Predicate outcome
            - ``details``: Predicate-defined, JSON-serializable dictionary
            - ``error``: Optional string (omitted when None)

    Notes:
        The contract expects ``List[PredicateResult]`` (Pydantic), not plain dicts.
    """


    out: list[PredicateResult] = []
    for e in evidence:
        pid = e.predicate
        try:
            mml = int(pid.split(":")[0].split("_")[1])
        except Exception:
            mml = 0
            
        # Summary counts for the contract: total, passed, failed.
        out.append(
            PredicateResult(
                id=pid,
                mml=mml,
                passed=bool(e.passed),    
                details=dict(e.details),
                error=(str(e.error) if getattr(e, "error", None) else None),
            )
        )
    return out
