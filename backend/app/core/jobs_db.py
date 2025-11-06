# app/core/jobs_db.py
from __future__ import annotations
import sqlite3, time, uuid, json, hashlib
from typing import Optional, Literal, TypedDict, NotRequired
from app.core import paths

# Wire-level status enum; 
# adding/removing values is a breaking change for clients.
JobStatus = Literal["queued", "running", "failed", "succeeded"]

# Normalized job payload returned to API callers.
# - timings is parsed JSON (dict); we never expose timings_json directly.
class JobRow(TypedDict):
    id: str
    sha256: str
    model_id: str
    vendor: str
    version: str
    status: JobStatus
    progress: int
    created_at: int
    updated_at: int
    # Nullable / optional fields from DB:
    message: NotRequired[str | None]
    # We expose parsed timings as "timings" (dict), not the raw JSON string:
    timings: NotRequired[dict | None]

# Single connection factory:
# - Ensures DB dir exists, applies WAL/NORMAL pragmas, and idempotently creates schema + indexes.
# - Keep table/index definitions in sync with read/write paths below.
def _connect() -> sqlite3.Connection:
    paths.JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(paths.JOBS_DB.as_posix(), timeout=30)

    # WAL = better concurrency for API reads while a background job writes.
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    
    # Lookups by (sha,vendor,version) enable idempotency skips.
    con.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        sha256 TEXT NOT NULL,
        model_id TEXT NOT NULL,
        vendor TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL,
        progress INTEGER NOT NULL DEFAULT 0,
        message TEXT,
        timings_json TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_sha ON jobs(sha256, vendor, version);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_model ON jobs(model_id);")
    return con

# Content-addressable key for uploads; used to deduplicate identical files.
def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# Compact shape returned by find_succeeded_by_sha; avoids over-fetching.
class JobLookup(TypedDict):
    id: str
    model_id: str
    status: JobStatus

# Returns the most recent job row for (sha,vendor,version).
# Caller decides whether to reuse only if status == "succeeded".
def find_succeeded_by_sha(sha256: str, vendor: str, version: str) -> Optional[JobLookup]:
    con = _connect()
    cur = con.execute("""
      SELECT id, model_id, status FROM jobs
      WHERE sha256=? AND vendor=? AND version=?
      ORDER BY updated_at DESC LIMIT 1
    """, (sha256, vendor, version))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    job_id, model_id, status = row
    return {"id": job_id, "model_id": model_id, "status": status}  # type: ignore[return-value]

# Inserts a queued job and returns its UUID. Timestamps are ms since epoch.
def create_job(sha256: str, model_id: str, vendor: str, version: str) -> str:
    job_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    con = _connect()
    con.execute("""
      INSERT INTO jobs (id, sha256, model_id, vendor, version, status, progress, created_at, updated_at)
      VALUES (?,?,?,?,?,?,?, ?,?)
    """, (job_id, sha256, model_id, vendor, version, "queued", 0, now, now))
    con.commit()
    con.close()
    return job_id

# Loads a job by id and maps DB columns → JobRow.
# - Parses timings_json into 'timings' dict when present.
# - Leaves absent/NULL fields out of the result.
def get_job(job_id: str) -> Optional[JobRow]:
    con = _connect()
    cur = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    row = cur.fetchone()
    cols = [c[0] for c in cur.description]
    con.close()
    if not row:
        return None

    raw = dict(zip(cols, row))
    out: JobRow = {
        "id": raw["id"],
        "sha256": raw["sha256"],
        "model_id": raw["model_id"],
        "vendor": raw["vendor"],
        "version": raw["version"],
        "status": raw["status"],
        "progress": int(raw["progress"]),
        "created_at": int(raw["created_at"]),
        "updated_at": int(raw["updated_at"]),
    }
    # Optional fields
    if raw.get("message") is not None:
        out["message"] = raw["message"]
    if raw.get("timings_json"):
        try:
            out["timings"] = json.loads(raw["timings_json"])
        except Exception:
            out["timings"] = None
    return out

# Patch-style update:
# - Always bumps updated_at (ms).
# - Only sets columns for provided kwargs; timings is JSON-encoded.
def update_status(
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    message: str | None = None,
    timings: dict | None = None,
):
    now = int(time.time() * 1000)
    con = _connect()
    sets = ["status=?", "updated_at=?"]
    vals: list[object] = [status, now]
    if progress is not None:
        sets.append("progress=?"); vals.append(int(progress))
    if message is not None:
        sets.append("message=?"); vals.append(message)
    if timings is not None:
        sets.append("timings_json=?"); vals.append(json.dumps(timings, ensure_ascii=False))
    vals.append(job_id)
    con.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", vals)
    con.commit()
    con.close()
