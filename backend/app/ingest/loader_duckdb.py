# ----------------------------- #
# Ingest: Sparx XML -> DuckDB   #
# Simple: XML -> JSONL -> DuckDB
# ----------------------------- #

from __future__ import annotations
import argparse
import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any
import duckdb

# uses the two-pass normalizer you built
from .discover_schema import normalized_rows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ingest")

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parents[1] / "data"            # backend/data
MODELS_DIR = DATA_DIR / "models"                # backend/data/models
MODELS_DIR.mkdir(parents=True, exist_ok=True)

PRAGMA_THREADS = 4
PRAGMA_MEM = "1GB"

# Streams the file in 1 MiB chunks to SHA-256 and returns the first 8 hex chars.
# Hash is content-based (path ignored); identical XML ⇒ identical model_id.
# Short IDs are convenient but not globally collision-proof—scope them to your models dir.
def compute_model_id(xml_path: Path) -> str:
    """sha256(xml)[:8] → stable short id per file content."""
    h = hashlib.sha256()
    with open(xml_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]

# If `overwrite=True` and the path exists, deletes the whole directory tree before recreating it.
# Side effect: data loss if pointed at the wrong path—validate inputs upstream.
def ensure_clean_dir(p: Path, overwrite: bool) -> None:
    if p.exists() and overwrite:
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def qi(name: str) -> str:
    """Quote identifier for DuckDB."""
    return '"' + name.replace('"', '""') + '"'


def load_xml_to_duckdb(xml_path: Path, model_dir: Path) -> Dict[str, int]:
    """
    Two-pass path:
        - normalized_rows() -> write per-table JSONL
        - COPY (SELECT * FROM read_json_auto(...)) TO ... PARQUET
        - create t_* views over Parquet
        - return counts
    """
    jsonl_dir = model_dir / "jsonl"
    parquet_dir = model_dir / "parquet"
    ensure_clean_dir(jsonl_dir, overwrite=True)
    ensure_clean_dir(parquet_dir, overwrite=True)

    # Pass 1/2: stream normalized rows and write JSONL files (one file per table)
    # Returns (schema, single-use iterator). You must consume `row_iter` once—materialize if needed again.
    # Keep `include_extensions` consistent across passes or row shapes will diverge.
    schema, row_iter = normalized_rows(xml_path)
    handles: Dict[str, Any] = {}
    paths: Dict[str, Path] = {}

    for table, row in row_iter:
        if table not in handles:
            p = jsonl_dir / f"{table}.jsonl"
            
            # Opens one JSONL file per table; thousands of tables can hit OS file-handle limits.
            # Ensure handles are closed (as done below) before starting DuckDB ingest.
            handles[table] = p.open("w", encoding="utf-8")
            
            paths[table] = p
        handles[table].write(json.dumps(row, ensure_ascii=False) + "\n")

    for f in handles.values():
        f.close()

    # Load into DuckDB & export to Parquet
    db_path = model_dir / "model.duckdb"
    
    # Creates/opens `<model_dir>/model.duckdb`. Single-writer DB—avoid concurrent writers.
    # Threads/memory PRAGMAs affect this connection only; always `close()` to flush metadata.
    con = duckdb.connect(str(db_path))
    con.execute(f"PRAGMA threads={PRAGMA_THREADS}")
    con.execute(f"PRAGMA memory_limit='{PRAGMA_MEM}'")

    # Speeds repeated queries but increases memory. 
    # If schemas/files are frequently recreated, stale cache can confuse debugging.
    con.execute("PRAGMA enable_object_cache=true")

    counts: Dict[str, int] = {}

    for table, p in paths.items():
        # If the file is empty (no rows), skip creating Parquet/view
        # Avoids generating Parquet/views for empty JSONL (no rows discovered).
        # Helpful for robustness, but also a signal to verify upstream ingest for that table.
        if p.stat().st_size == 0:
            log.info("no rows for table=%s; skipping", table)
            continue

        # Use forward slashes for DuckDB on Windows
        json_path = p.as_posix()
        
        pq_path = (parquet_dir / f"{table}.parquet").as_posix()
        
        # escape single quotes for sql statements
        # Escapes single quotes for embedding literal paths in SQL (paired with `.as_posix()` for Windows).
        # Still a literal-injection surface—only interpolate trusted paths.
        json_sql = json_path.replace("'", "''")
        
        pq_sql   = pq_path.replace("'", "''")

        # 1) Write Parquet directly from JSONL (NO PARAMS in COPY)
        # `read_json_auto(..., union_by_name=true)` merges fields by name; missing/new fields widen schema and may coerce types.
        # `COPY ... TO` doesn’t accept parameters; literals are required. ZSTD compression trades CPU for smaller files.
        con.execute(f"""
            COPY (
            SELECT * FROM read_json_auto('{json_sql}', union_by_name = true)
            ) TO '{pq_sql}' (FORMAT PARQUET, COMPRESSION 'zstd');
        """)


        # 2) Register canonical view over Parquet (literal path)
        # View depends on the literal Parquet path; moving/deleting files later will break the view.
        # `{qi(table)}` safely quotes table names to handle reserved words/special chars.
        con.execute(
            f"CREATE OR REPLACE VIEW {qi(table)} AS SELECT * FROM read_parquet('{pq_sql}')"
        )


        # 3) Count via the view
        cnt = con.execute(f"SELECT COUNT(*) FROM {qi(table)};").fetchone()[0]
        counts[table] = int(cnt)
        log.info("loaded table=%s rows=%s → %s", table, cnt, pq_path.split('/')[-1])

    # Collect stats for better planning on subsequent queries
    try:
        con.execute("ANALYZE;")
    except Exception:
        # ANALYZE can fail if no tables created; ignore
        pass

    con.close()
    return counts


def main():
    ap = argparse.ArgumentParser("ingest-xml-to-duckdb")
    ap.add_argument(
        "--xml",
        default=str(HERE.parents[1] / "samples" / "sparx" / "v17_1" / "DellSat-77_System.xml"),
        help="Path to Sparx XML export",
    )
    ap.add_argument("--model-id", default=None, help="Model identifier (default: sha256(xml)[:8])")
    ap.add_argument("--overwrite", action="store_true", help="If model directory exists, delete and recreate it.")
    args = ap.parse_args()

    xml_path = Path(args.xml).resolve()
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    model_id = args.model_id or compute_model_id(xml_path)
    model_dir = MODELS_DIR / model_id
    ensure_clean_dir(model_dir, overwrite=args.overwrite)

    counts = load_xml_to_duckdb(xml_path, model_dir)

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
