# ------------------------------------------------------------
# Module: backend/app/ingest/loader_duckdb.py
# Purpose: Ingest an XML export into DuckDB via JSONL→Parquet, create views, and return row counts.
# ------------------------------------------------------------

"""Stream–normalize XML to per-table JSONL, convert to Parquet, and register DuckDB views.

Responsibilities
----------------
- Compute a stable model id from XML content.
- Stream normalized rows and write per-table JSONL.
- Copy JSONL to Parquet and (re)create DuckDB views.
- Return per-table row counts and key output paths; provide a small CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.flow.ingest.duckdb_connection import open_duckdb
from app.flow.ingest.duckdb_utils import (
    copy_jsonl_to_parquet,
    count_rows,
    create_or_replace_view,
)
from app.flow.ingest.jsonl_writer import write_jsonl_tables
from app.flow.ingest.normalize_rows import normalized_rows
from app.flow.ingest.types import IngestResult
from app.infra.core.config import settings
from app.infra.core.paths import MODELS_DIR
from app.infra.utils.hashing import compute_sha256_stream
from app.infra.utils.timing import log_timer as _timer

log = logging.getLogger(__name__)


def compute_model_id(xml_path: Path) -> str:
    """sha256(xml)[:8] computed in a streaming fashion."""
    with open(xml_path, "rb") as f:
        return compute_sha256_stream(f)[:8]


# NOTE: identifier quoting is handled inside from app.flow.ingest.parquet_views


def load_xml_to_duckdb(xml_path: Path, model_dir: Path) -> dict[str, int]:
    """
    Two-pass path:
        - normalized_rows() -> write per-table JSONL
        - COPY (SELECT * FROM read_json_auto(...)) TO ... PARQUET
        - create t_* views over Parquet
        - return counts
    """
    log.info("ingest start xml='%s' model_dir='%s'", str(xml_path), str(model_dir))
    jsonl_dir = model_dir / "jsonl"
    parquet_dir = model_dir / "parquet"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1/2: discover schema + stream rows to JSONL (consume iterator once).
    with _timer("discover+stream-schema", xml=str(xml_path)):
        try:
            schema, row_iter = normalized_rows(xml_path)
        except Exception:
            log.error("schema discovery failed xml='%s'", str(xml_path), exc_info=True)
            raise
    log.info("discovered tables=%d", len(schema))

    # Write per-table JSONL (LRU-managed handles).
    with _timer("write-jsonl"):
        paths = write_jsonl_tables(row_iter, jsonl_dir)

    # Open DuckDB and prepare Parquet export.
    db_path = model_dir / "model.duckdb"
    con = open_duckdb(
        db_path,
        threads=getattr(settings, "DUCKDB_THREADS", 4),
        mem=getattr(settings, "DUCKDB_MEM", "1GB"),
    )

    counts: dict[str, int] = {}

    for table, p in paths.items():
        # Skip empty or missing JSONL files.
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            log.error("jsonl missing before load table='%s' path='%s'", table, str(p))
            continue
        if size == 0:
            log.info("no rows for table=%s; skipping", table)
            continue

        json_path = p.as_posix()

        pq_path = (parquet_dir / f"{table}.parquet").as_posix()

        # Escape single quotes for SQL literals.
        json_sql = json_path.replace("'", "''")
        pq_sql = pq_path.replace("'", "''")

        # 1) Write Parquet from JSONL.
        with _timer("copy-jsonl-to-parquet", table=table, bytes=size):
            copy_jsonl_to_parquet(con, json_sql, pq_sql)

        # 2) Create/replace view over Parquet.
        create_or_replace_view(con, table, pq_sql)

        # 3) Count via the view.
        rows = int(count_rows(con, table))
        counts[table] = rows
        log.info("loaded table=%s rows=%s → %s", table, rows, pq_path.split("/")[-1])

    # Collect stats (may be a no-op if no tables).
    try:
        con.execute("ANALYZE;")
    except Exception:
        # ANALYZE can fail if no tables created; log and continue
        log.debug(
            "ANALYZE skipped or failed; possibly no tables created", exc_info=True
        )

    con.close()
    return counts


def ingest_xml(
    xml_path: Path, model_id: str | None = None, overwrite: bool = False
) -> IngestResult:
    """Pure entry point for tools/API to call; no argparse/print."""
    xml_path = xml_path.resolve()
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")
    model_id = model_id or compute_model_id(xml_path)
    model_dir = MODELS_DIR / model_id
    # NOTE: deletion/purge is the caller's responsibility.

    with _timer(
        "load-xml-to-duckdb",
        xml=str(xml_path),
        model_dir=str(model_dir),
        model_id=model_id,
    ):
        counts = load_xml_to_duckdb(xml_path, model_dir)
    return {
        "model_id": model_id,
        "duckdb_path": str(model_dir / "model.duckdb"),
        "jsonl_dir": str(model_dir / "jsonl"),
        "parquet_dir": str(model_dir / "parquet"),
        "tables": counts,
    }


# ---- CLI for `python -m from app.flow.ingest.loader_duckdb` ----
def _main():
    ap = argparse.ArgumentParser("ingest-xml")
    ap.add_argument("--xml", required=True, help="Path to Sparx XML export")
    ap.add_argument(
        "--model-id", help="Override model identifier (default: sha256[:8])"
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Purge output dir first (caller responsibility if desired)",
    )
    args = ap.parse_args()

    try:
        res = ingest_xml(
            Path(args.xml), model_id=args.model_id, overwrite=args.overwrite
        )
    except Exception:
        logging.getLogger(__name__).exception("ingest failed")
        sys.exit(1)
    else:
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    _main()
