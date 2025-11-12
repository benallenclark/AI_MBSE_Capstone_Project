# ------------------------------------------------------------
# Module: app/core/jobs_db.py
# Purpose: SQLite-backed job store with normalized serializers for API responses.
# ------------------------------------------------------------

"""Lightweight persistence layer for background jobs using SQLite.

Responsibilities
----------------
- Initialize and maintain the jobs table and its indexes
- Provide read/write helpers for creating and updating job records
- Normalize database rows into API-facing shapes
- Offer targeted lookups to avoid over-fetching (e.g., by sha or latest per model)

Notes
-----
- Timestamps are milliseconds since the Unix epoch.
- WAL mode enables concurrent readers while writers update rows.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Mapping
from typing import Any, Literal, NotRequired, TypedDict

from app.core import paths

# Public, wire-level status values for jobs; changing these is a breaking change.
JobStatus = Literal["queued", "running", "failed", "succeeded"]


class JobRow(TypedDict):
    """Normalized API view of a job row with optional fields omitted when null.

    Notes
    -----
    - `timings` is parsed from `timings_json` if present; parse failures yield None.
    - `progress`, `created_at`, and `updated_at` are ints (ms).
    """

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


def _connect() -> sqlite3.Connection:
    """Open a SQLite connection with dict-like rows and sane PRAGMAs (no DDL).

    Notes
    -----
    - Enables WAL and sets synchronous=NORMAL for better read concurrency.
    - Uses `sqlite3.Row` so callers can access columns by name.
    """

    paths.JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(paths.JOBS_DB.as_posix(), timeout=30)
    con.row_factory = sqlite3.Row  # dict-like rows
    # WAL = better concurrency for API reads while a background job writes.
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    """Create the jobs table and indexes if missing (idempotent)."""
    con.execute(
        """
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
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_sha ON jobs(sha256, vendor, version);"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_model ON jobs(model_id);")


def ensure_initialized() -> None:
    """Initialize on-disk DB and schema once at app startup (idempotent).

    Notes
    -----
    - Applies WAL/synchronous PRAGMAs at the DB level.
    """
    paths.JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(paths.JOBS_DB.as_posix(), timeout=30) as con:
        # Set PRAGMAs once; journal_mode=WAL persists at the DB level.
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        _ensure_schema(con)
        con.commit()


def _row_to_jobrow(raw: Any) -> JobRow:
    """Initialize on-disk DB and schema once at app startup (idempotent).

    Notes
    -----
    - Applies WAL/synchronous PRAGMAs at the DB level.
    """
    # Normalize to a plain dict so we can use .get safely.
    if isinstance(raw, sqlite3.Row):
        data = {k: raw[k] for k in raw.keys()}
    elif isinstance(raw, Mapping):
        data = dict(raw)  # copy to detach from underlying cursor
    else:
        try:
            data = dict(raw)  # last resort (may work for custom mappings)
        except Exception as e:
            raise TypeError(f"Unsupported row type: {type(raw).__name__}") from e

    out: JobRow = {
        "id": data["id"],
        "sha256": data["sha256"],
        "model_id": data["model_id"],
        "vendor": data["vendor"],
        "version": data["version"],
        "status": data["status"],
        "progress": int(data["progress"]),
        "created_at": int(data["created_at"]),
        "updated_at": int(data["updated_at"]),
    }
    # Optional fields
    if data.get("message") is not None:
        out["message"] = data["message"]
    tj = data.get("timings_json")
    if tj:
        try:
            out["timings"] = json.loads(tj)
        except Exception:
            out["timings"] = None
    return out


class JobLookup(TypedDict):
    """Minimal shape for quick lookups (id, model_id, status)."""

    id: str
    model_id: str
    status: JobStatus


def find_succeeded_by_sha(sha256: str, vendor: str, version: str) -> JobLookup | None:
    """Return most recent job for (sha256, vendor, version); None if absent.

    Notes
    -----
    - Uses `updated_at` ordering to pick the latest record.
    """
    with _connect() as con:
        cur = con.execute(
            """
            SELECT id, model_id, status FROM jobs
            WHERE sha256=? AND vendor=? AND version=?
            ORDER BY updated_at DESC LIMIT 1
            """,
            (sha256, vendor, version),
        )
        row = cur.fetchone()
    if not row:
        return None
    job_id, model_id, status = row["id"], row["model_id"], row["status"]
    return {"id": job_id, "model_id": model_id, "status": status}  # type: ignore[return-value]


def create_job(sha256: str, model_id: str, vendor: str, version: str) -> str:
    """Insert a queued job and return its UUID.

    Notes
    -----
    - Initial status is "queued" with progress=0.
    - Timestamps stored as ms since epoch.
    """
    job_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    with _connect() as con:
        con.execute(
            """
            INSERT INTO jobs (id, sha256, model_id, vendor, version, status, progress, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?, ?,?)
            """,
            (job_id, sha256, model_id, vendor, version, "queued", 0, now, now),
        )
        con.commit()
    return job_id


def get_job(job_id: str) -> JobRow | None:
    """Load a job by id; parses timings and omits NULL fields."""
    with _connect() as con:
        cur = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
    if not row:
        return None

    return _row_to_jobrow(row)


def get_latest_job(model_id: str) -> JobRow | None:
    """Return most recent job for model_id (or None)."""
    with _connect() as con:
        cur = con.execute(
            "SELECT * FROM jobs WHERE model_id=? ORDER BY updated_at DESC LIMIT 1",
            (model_id,),
        )
        row = cur.fetchone()
    return _row_to_jobrow(row) if row else None


def update_status(
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    message: str | None = None,
    timings: dict | None = None,
):
    """Patch a job's fields and bump `updated_at` (ms).

    Notes
    -----
    - Only provided fields are modified; others remain unchanged.
    - `timings` is JSON-encoded to `timings_json`.
    - No error is raised if `job_id` does not exist (silent no-op).
    """
    now = int(time.time() * 1000)
    with _connect() as con:
        sets = ["status=?", "updated_at=?"]
        vals: list[object] = [status, now]
        if progress is not None:
            sets.append("progress=?")
            vals.append(int(progress))
        if message is not None:
            sets.append("message=?")
            vals.append(message)
        if timings is not None:
            sets.append("timings_json=?")
            vals.append(json.dumps(timings, ensure_ascii=False))
        vals.append(job_id)
        con.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", vals)
        con.commit()
