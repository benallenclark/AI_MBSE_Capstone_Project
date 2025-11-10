# ----------------------------- #
# Ingest: Sparx XML -> DuckDB   #
# Simple: XML -> JSONL -> DuckDB
# ----------------------------- #

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

# uses the two-pass normalizer you built
from .discover_schema import normalized_rows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ingest")

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parents[1] / "data"  # backend/data
MODELS_DIR = DATA_DIR / "models"  # backend/data/models
MODELS_DIR.mkdir(parents=True, exist_ok=True)

PRAGMA_THREADS = 4
PRAGMA_MEM = "1GB"


@contextmanager
def _timer(msg: str, **ctx: Any):
    """
    Log start + duration for a block with optional context fields.
    Usage: with _timer("copy-parquet", table=table): ...
    """
    t0 = time.perf_counter()
    if ctx:
        log.info("%s start %s", msg, ctx)
    else:
        log.info("%s start", msg)
    try:
        yield
    except Exception:
        # Include elapsed time on failure for triage
        dt = time.perf_counter() - t0
        if ctx:
            log.error("%s failed after %.3fs %s", msg, dt, ctx, exc_info=True)
        else:
            log.error("%s failed after %.3fs", msg, dt, exc_info=True)
        raise
    else:
        dt = time.perf_counter() - t0
        if ctx:
            log.info("%s ok in %.3fs %s", msg, dt, ctx)
        else:
            log.info("%s ok in %.3fs", msg, dt)


# Streams the file in 1 MiB chunks to SHA-256 and returns the first 8 hex chars.
# Hash is content-based (path ignored); identical XML ⇒ identical model_id.
# Short IDs are convenient but not globally collision-proof—scope them to your models dir.
def compute_model_id(xml_path: Path) -> str:
    """sha256(xml)[:8] → stable short id per file content."""
    log.debug("hashing file start {'xml': '%s'}", str(xml_path))
    h = hashlib.sha256()
    total = 0
    with open(xml_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            total += len(chunk)
    log.info("hashed file bytes=%s sha256_8=%s", total, h.hexdigest()[:8])
    return h.hexdigest()[:8]


def qi(name: str) -> str:
    """Quote identifier for DuckDB."""
    return '"' + name.replace('"', '""') + '"'


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
    # Create output dirs early
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1/2: stream normalized rows and write JSONL files (one file per table)
    # Returns (schema, single-use iterator). You must consume `row_iter` once—materialize if needed again.
    # Keep `include_extensions` consistent across passes or row shapes will diverge.
    with _timer("discover+stream-schema", xml=str(xml_path)):
        try:
            schema, row_iter = normalized_rows(xml_path)
        except Exception:
            log.error("schema discovery failed xml='%s'", str(xml_path), exc_info=True)
            raise
    log.info("discovered tables=%d", len(schema))
    handles: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    written_rows: dict[str, int] = {}

    try:
        with _timer("write-jsonl"):
            for table, row in row_iter:
                if table not in handles:
                    p = jsonl_dir / f"{table}.jsonl"

                    # Opens one JSONL file per table; thousands of tables can hit OS file-handle limits.
                    # Ensure handles are closed (as done below) before starting DuckDB ingest.
                    try:
                        handles[table] = p.open("w", encoding="utf-8")
                    except OSError:
                        # EMFILE: too many open files
                        log.error(
                            "open jsonl failed table='%s' path='%s'",
                            table,
                            str(p),
                            exc_info=True,
                        )
                        raise
                    paths[table] = p
                    written_rows[table] = 0

                try:
                    handles[table].write(json.dumps(row, ensure_ascii=False) + "\n")
                    written_rows[table] += 1
                except Exception:
                    log.error(
                        "write jsonl failed table='%s' path='%s'",
                        table,
                        str(paths[table]),
                        exc_info=True,
                    )
                    raise
    finally:
        for t, f in handles.items():
            try:
                f.close()
            except Exception:
                log.warning(
                    "close jsonl handle failed table='%s' path='%s'",
                    t,
                    str(paths.get(t)),
                )
        if written_rows:
            log.info(
                "jsonl written tables=%d totals=%s",
                len(written_rows),
                {t: n for t, n in sorted(written_rows.items())},
            )

    for f in handles.values():
        f.close()

    # Load into DuckDB & export to Parquet
    db_path = model_dir / "model.duckdb"

    # Creates/opens `<model_dir>/model.duckdb`. Single-writer DB—avoid concurrent writers.
    # Threads/memory PRAGMAs affect this connection only; always `close()` to flush metadata.
    try:
        con = duckdb.connect(str(db_path))
    except Exception:
        log.error("duckdb connect failed db='%s'", str(db_path), exc_info=True)
        raise
    try:
        con.execute(f"PRAGMA threads={PRAGMA_THREADS}")
        con.execute(f"PRAGMA memory_limit='{PRAGMA_MEM}'")

        # Speeds repeated queries but increases memory.
        # If schemas/files are frequently recreated, stale cache can confuse debugging.
        con.execute("PRAGMA enable_object_cache=true")
    except Exception:
        log.warning("duckdb pragmas failed; continuing with defaults", exc_info=True)

    counts: dict[str, int] = {}

    for table, p in paths.items():
        # If the file is empty (no rows), skip creating Parquet/view
        # Avoids generating Parquet/views for empty JSONL (no rows discovered).
        # Helpful for robustness, but also a signal to verify upstream ingest for that table.
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            log.error("jsonl missing before load table='%s' path='%s'", table, str(p))
            continue
        if size == 0:
            log.info("no rows for table=%s; skipping", table)
            continue

        # Use forward slashes for DuckDB on Windows
        json_path = p.as_posix()

        pq_path = (parquet_dir / f"{table}.parquet").as_posix()

        # escape single quotes for sql statements
        # Escapes single quotes for embedding literal paths in SQL (paired with `.as_posix()` for Windows).
        # Still a literal-injection surface—only interpolate trusted paths.
        json_sql = json_path.replace("'", "''")

        pq_sql = pq_path.replace("'", "''")

        # 1) Write Parquet directly from JSONL (NO PARAMS in COPY)
        # `read_json_auto(..., union_by_name=true)` merges fields by name; missing/new fields widen schema and may coerce types.
        # `COPY ... TO` doesn’t accept parameters; literals are required. ZSTD compression trades CPU for smaller files.
        with _timer("copy-jsonl-to-parquet", table=table, bytes=size):
            try:
                con.execute(f"""
                    COPY (
                    SELECT * FROM read_json_auto('{json_sql}', union_by_name = true)
                    ) TO '{pq_sql}' (FORMAT PARQUET, COMPRESSION 'zstd');
                """)
            except Exception:
                log.error(
                    "duckdb COPY failed table='%s' json='%s' parquet='%s'",
                    table,
                    json_path,
                    pq_path,
                    exc_info=True,
                )
                raise

        # 2) Register canonical view over Parquet (literal path)
        # View depends on the literal Parquet path; moving/deleting files later will break the view.
        # `{qi(table)}` safely quotes table names to handle reserved words/special chars.
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW {qi(table)} AS SELECT * FROM read_parquet('{pq_sql}')"
            )
        except Exception:
            log.error(
                "create view failed table='%s' parquet='%s'",
                table,
                pq_path,
                exc_info=True,
            )
            raise

        # 3) Count via the view
        try:
            cnt = con.execute(f"SELECT COUNT(*) FROM {qi(table)};").fetchone()[0]
        except Exception:
            log.error("row count failed table='%s'", table, exc_info=True)
            raise
        counts[table] = int(cnt)
        log.info("loaded table=%s rows=%s → %s", table, cnt, pq_path.split("/")[-1])

    # Collect stats for better planning on subsequent queries
    try:
        con.execute("ANALYZE;")
    except Exception:
        # ANALYZE can fail if no tables created; log and continue
        log.debug(
            "ANALYZE skipped or failed; possibly no tables created", exc_info=True
        )

    try:
        con.close()
    except Exception:
        log.warning("duckdb close failed db='%s'", str(db_path), exc_info=True)
    return counts


def main():
    ap = argparse.ArgumentParser("ingest-xml-to-duckdb")
    ap.add_argument(
        "--xml",
        default=str(
            HERE.parents[1] / "samples" / "sparx" / "v17_1" / "DellSat-77_System.xml"
        ),
        help="Path to Sparx XML export",
    )
    ap.add_argument(
        "--model-id", default=None, help="Model identifier (default: sha256(xml)[:8])"
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="If model directory exists, delete and recreate it.",
    )
    args = ap.parse_args()

    xml_path = Path(args.xml).resolve()
    if not xml_path.exists():
        log.error("xml path not found '%s'", str(xml_path))
        raise FileNotFoundError(f"XML not found: {xml_path}")

    model_id = args.model_id or compute_model_id(xml_path)
    model_dir = MODELS_DIR / model_id
    if args.overwrite:
        # Note: actual deletion is not implemented here; we log to avoid surprise.
        log.warning(
            "--overwrite flag provided but not implemented; existing files may be reused model_dir='%s'",
            str(model_dir),
        )

    with _timer(
        "load-xml-to-duckdb",
        xml=str(xml_path),
        model_dir=str(model_dir),
        model_id=model_id,
    ):
        try:
            counts = load_xml_to_duckdb(xml_path, model_dir)
        except Exception:
            log.error("ingest failed model_id=%s", model_id, exc_info=True)
            raise

    result = {
        "model_id": model_id,
        "duckdb_path": str(model_dir / "model.duckdb"),
        "jsonl_dir": str(model_dir / "jsonl"),
        "parquet_dir": str(model_dir / "parquet"),
        "tables": counts,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
