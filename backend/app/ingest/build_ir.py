# ------------------------------------------------------------
# Module: build_ir.py (minimal)
# Purpose: Create IR views over loader tables, then build helpers.
# ------------------------------------------------------------
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import duckdb

log = logging.getLogger("ingest.build_ir")
logging.basicConfig(level=logging.INFO)

PRAGMA_THREADS = 4
PRAGMA_MEM = "1GB"

# Opens a DuckDB connection and tunes per-connection PRAGMAs (threads/memory/cache).
# Side effect: affects performance/memory; callers MUST close the connection to release resources.
# Size PRAGMA_MEM to your host/model or you may hit OOM or slow spills.
def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(f"PRAGMA threads={PRAGMA_THREADS};")
    con.execute(f"PRAGMA memory_limit='{PRAGMA_MEM}';")
    
    # Caches compiled objects for speed but increases memory usage.
    # If you rebuild schemas often (DROP/CREATE), 
    # stale cache can cause surprises;
    # disable when debugging memory/schema issues.
    con.execute("PRAGMA enable_object_cache=true;")
    return con

# ----------------------------- #
# Build IR = lightweight views
# ----------------------------- #
def create_ir_views(con):
    # Nukes the entire `ir` schema (views/tables) before recreating—safe only if `ir.*` is derived.
    # Concurrent readers of `ir.*` will see it disappear briefly; avoid running during active queries.
    con.execute("DROP SCHEMA IF EXISTS ir CASCADE;")
    
    con.execute("CREATE SCHEMA IF NOT EXISTS ir;")
    
    # Enumerates `main` tables/views that start with `t_` (the loader’s outputs).
    # The ESCAPE clause makes the underscore literal in LIKE. If the loader didn’t run, this returns empty.
    rows = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name LIKE 't\\_%' ESCAPE '\\'
          AND table_type in ('BASE TABLE', 'VIEW')
        ORDER BY table_name
    """).fetchall()

    created = []
    for (tbl,) in rows:
        # Quotes each discovered table name to survive special chars/reserved words.
        # Avoids SQL injection via metadata; do not interpolate untrusted names without quoting.
        q = '"' + tbl.replace('"','""') + '"'
        con.execute(f"CREATE OR REPLACE VIEW ir.{q} AS SELECT * FROM main.{q};")
        created.append(tbl)

    logging.info("IR views created for: " + (", ".join(created) if created else "(none)"))
    return created



# ----------------------------- #
# Helper tables (irx.*)
# ----------------------------- #
HELPERS = {
    "blocks": """
        CREATE OR REPLACE TABLE irx.blocks AS
        SELECT
          o.Object_ID  AS block_oid,
          UPPER(REPLACE(REPLACE(TRIM(o.ea_guid), '{',''),'}','')) AS block_guid,
          TRIM(o.Name) AS block_name,
          o.Stereotype AS block_stereotype
        FROM ir.t_object o
        WHERE LOWER(o.Stereotype) IN ('block');
    """,
    "ports": """
        CREATE OR REPLACE TABLE irx.ports AS
        SELECT
          p.Object_ID AS port_oid,
          UPPER(REPLACE(REPLACE(TRIM(p.ea_guid),'{',''),'}','')) AS port_guid,
          TRIM(p.Name) AS port_name,
          p.ParentID   AS parent_block_oid,
          p.Classifier AS classifier_oid,
          CASE
            WHEN p.PDATA1 IS NULL THEN NULL
            WHEN TRIM(p.PDATA1) IN ('', '<none>', '&lt;none&gt;') THEN NULL
            ELSE UPPER(REPLACE(REPLACE(TRIM(p.PDATA1),'{',''),'}',''))
          END AS pdata1_guid,
          p.Stereotype AS port_stereotype
        FROM ir.t_object p
        WHERE LOWER(p.Stereotype) IN ('port','proxyport','fullport');
    """,
    "port_edges": """
        CREATE OR REPLACE TABLE irx.port_edges AS
        SELECT
          c.Connector_ID AS conn_oid,
          c.Start_Object_ID AS src_port_oid,
          c.End_Object_ID   AS dst_port_oid,
          TRIM(c.Connector_Type) AS conn_type
        FROM ir.t_connector c
        WHERE c.Connector_Type IN ('Connector','Association');
    """,
    "gen_edges": """
        CREATE OR REPLACE TABLE irx.gen_edges AS
        SELECT
          c.Start_Object_ID AS child_oid,
          c.End_Object_ID   AS parent_oid
        FROM ir.t_connector c
        WHERE c.Connector_Type = 'Generalization';
    """,
    "trace_edges": """
        CREATE OR REPLACE TABLE irx.trace_edges AS
        SELECT
          c.Start_Object_ID AS src_oid,
          c.End_Object_ID   AS dst_oid,
          LOWER(TRIM(c.Stereotype)) AS kind
        FROM ir.t_connector c
        WHERE LOWER(TRIM(c.Stereotype)) IN ('trace','satisfy','refine','allocate');
    """,
}

# Creates/overwrites materialized helper tables under `irx.*` (idempotent writes).
# Side effects: DDL + potentially large scans; expect I/O and time on big models.
def build_helpers(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    con.execute("CREATE SCHEMA IF NOT EXISTS irx;")

    # Only build helpers if required IR sources exist; otherwise create empty shells.
    # Fast precheck via information_schema to avoid throwing on missing sources.
    # Be aware of case sensitivity: DuckDB stores unquoted identifiers in lowercase.
    def _table_exists(schema: str, name: str) -> bool:
        return bool(con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?",
            [schema, name]
        ).fetchone())

    def _column_exists(schema: str, table: str, column: str) -> bool:
        return bool(con.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema=? AND table_name=? AND column_name=?",
            [schema, table, column]
        ).fetchone())

    # blocks/ports need ir.t_object
    if _table_exists("ir", "t_object"):
        con.execute(HELPERS["blocks"])

        # Check if PDATA1 column exists before using it
        if _column_exists("ir", "t_object", "pdata1"):
            con.execute(HELPERS["ports"])
        else:
            # Create ports table without PDATA1 column
            con.execute("""
                CREATE OR REPLACE TABLE irx.ports AS
                SELECT
                  p.Object_ID AS port_oid,
                  UPPER(REPLACE(REPLACE(TRIM(p.ea_guid),'{',''),'}','')) AS port_guid,
                  TRIM(p.Name) AS port_name,
                  p.ParentID   AS parent_block_oid,
                  p.Classifier AS classifier_oid,
                  NULL AS pdata1_guid,
                  p.Stereotype AS port_stereotype
                FROM ir.t_object p
                WHERE LOWER(p.Stereotype) IN ('port','proxyport','fullport');
            """)
    else:
        # Creates empty helper tables when sources are missing to keep downstream SQL running.
        #  Useful for robustness, but can hide upstream ingest issues—log/alert on zero-row helpers in production.
        con.execute("CREATE OR REPLACE TABLE irx.blocks (block_oid BIGINT, block_guid TEXT, block_name TEXT, block_stereotype TEXT);")
        con.execute("CREATE OR REPLACE TABLE irx.ports (port_oid BIGINT, port_guid TEXT, port_name TEXT, parent_block_oid BIGINT, classifier_oid BIGINT, pdata1_guid TEXT, port_stereotype TEXT);")

    # edges need ir.t_connector
    if _table_exists("ir", "t_connector"):
        con.execute(HELPERS["port_edges"])
        con.execute(HELPERS["gen_edges"])
        con.execute(HELPERS["trace_edges"])
    else:
        con.execute("CREATE OR REPLACE TABLE irx.port_edges (conn_oid BIGINT, src_port_oid BIGINT, dst_port_oid BIGINT, conn_type TEXT);")
        con.execute("CREATE OR REPLACE TABLE irx.gen_edges (child_oid BIGINT, parent_oid BIGINT);")
        con.execute("CREATE OR REPLACE TABLE irx.trace_edges (src_oid BIGINT, dst_oid BIGINT, kind TEXT);")

    # quick counts
    counts = {}
    for t in ("irx.blocks", "irx.ports", "irx.port_edges", "irx.gen_edges", "irx.trace_edges"):
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    log.info(f"helpers: {counts}")
    return counts

# Preconditions: `<model_dir>/model.duckdb` must exist (built by the loader).
# Side effects: (re)creates `ir.*` views, materializes `irx.*`, runs `ANALYZE` for optimizer stats, then closes the connection.
# Returns the DB path; consumers can chain further queries without reopening if they manage their own handle.
def build_ir(model_dir: Path) -> Path:
    """
    Expect: model_dir/model.duckdb (produced by loader_duckdb.py)
    Output: ir.* (views), irx.* (materialized helper tables) in the same DB.
    """
    db_path = model_dir / "model.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB not found: {db_path}. Run loader first.")

    con = connect(db_path)
    created = create_ir_views(con)
    if not created:
        log.warning("No base tables found to mirror into ir.* (did the loader create any t_* tables?)")
    counts = build_helpers(con)
    con.execute("ANALYZE;")
    con.close()
    return db_path

# ----------------------------- #
# CLI
# ----------------------------- #
def main():
    ap = argparse.ArgumentParser("build-ir")
    ap.add_argument("--model-dir", required=True, help="Directory containing model.duckdb (from loader)")
    args = ap.parse_args()
    p = build_ir(Path(args.model_dir).resolve())
    print(str(p))

if __name__ == "__main__":
    main()
