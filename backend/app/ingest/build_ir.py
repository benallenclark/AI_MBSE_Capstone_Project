# ------------------------------------------------------------
# Module: build_ir.py (minimal)
# Purpose: Create IR views over loader tables, then build helpers.
# ------------------------------------------------------------
"""Build IR (views) and helper tables on top of a DuckDB loader output.

Responsibilities
----------------
- Open a tuned DuckDB connection for build operations.
- Create lightweight `ir.*` views that mirror `main.t_*` loader tables.
- Materialize `irx.*` helper tables used by downstream SQL.
- Offer a CLI to run the whole build for a given model directory.

Notes
-----
- PRAGMA memory units are human-readable (e.g., "1GB").
- Operations are destructive to the `ir` schema (dropped and recreated).
- Helper table writes are idempotent (tables are replaced).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb

log = logging.getLogger("ingest.build_ir")
logging.basicConfig(level=logging.INFO)

PRAGMA_THREADS = 4
PRAGMA_MEM = "1GB"


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection and apply per-connection PRAGMAs.

    Notes
    -----
    - Tunes `threads`, `memory_limit`, and enables the object cache.
    - Side effects: impacts performance and memory footprint for this handle.
    - Callers MUST close the connection to release resources.
    """
    con = duckdb.connect(str(db_path))
    con.execute(f"PRAGMA threads={PRAGMA_THREADS};")
    con.execute(f"PRAGMA memory_limit='{PRAGMA_MEM}';")

    # Cache compiled objects for speed (higher memory use). Disable if debugging
    # schema/memory issues, as stale cache can surprise during frequent DDL.
    con.execute("PRAGMA enable_object_cache=true;")
    return con


def create_ir_views(con):
    """Recreate `ir.*` views that mirror `main.t_*` loader outputs.

    Drops and recreates the `ir` schema, then creates `ir.<name>` views for each
    discovered `main.t_*` table/view. Returns a list of created view names.

    Notes
    -----
    - Safe only if `ir.*` is fully derived (schema is dropped with CASCADE).
    - Briefly disrupts concurrent readers of `ir.*`.
    - Quotes identifiers to avoid issues with reserved words/special chars.
    """
    # Remove the entire `ir` schema before rebuilding (derived data only).
    con.execute("DROP SCHEMA IF EXISTS ir CASCADE;")
    con.execute("CREATE SCHEMA IF NOT EXISTS ir;")

    # Discover loader outputs under `main` prefixed with `t_`.
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
        # Quote names to avoid collisions with reserved words/special chars.
        q = '"' + tbl.replace('"', '""') + '"'
        con.execute(f"CREATE OR REPLACE VIEW ir.{q} AS SELECT * FROM main.{q};")
        created.append(tbl)

    logging.info(
        "IR views created for: " + (", ".join(created) if created else "(none)")
    )
    return created


# ----------------------------- #
# Helper tables (irx.*)
# ----------------------------- #
# Each entry materializes a helper table:
# - blocks:    Block objects (filtered from t_object).
# - ports:     Port-like objects with parent/classifier linkage.
# - port_edges:Connector/Association edges between ports.
# - gen_edges: Generalization parent-child edges.
# - trace_edges:Trace/satisfy/refine/allocate edges (typed).
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


def build_helpers(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Create/overwrite materialized helper tables under `irx.*`.

    Notes
    -----
    - Idempotent writes (tables are replaced).
    - Builds only when required IR sources exist; otherwise creates empty shells.
    - Performs full scans; expect I/O/time on large models.
    - Returns row counts per helper table.
    """
    con.execute("CREATE SCHEMA IF NOT EXISTS irx;")

    # Fast precheck for required sources to avoid throwing on missing tables.
    # DuckDB stores unquoted identifiers in lowercase in information_schema.
    def _table_exists(schema: str, name: str) -> bool:
        return bool(
            con.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?",
                [schema, name],
            ).fetchone()
        )

    # blocks/ports need ir.t_object
    if _table_exists("ir", "t_object"):
        con.execute(HELPERS["blocks"])
        con.execute(HELPERS["ports"])
    else:
        # Keep downstream SQL runnable: create empty shells if sources are missing.
        # Useful for robustness, but monitor for zero-row helpers in production.
        con.execute(
            "CREATE OR REPLACE TABLE irx.blocks (block_oid BIGINT, block_guid TEXT, block_name TEXT, block_stereotype TEXT);"
        )
        con.execute(
            "CREATE OR REPLACE TABLE irx.ports (port_oid BIGINT, port_guid TEXT, port_name TEXT, parent_block_oid BIGINT, classifier_oid BIGINT, pdata1_guid TEXT, port_stereotype TEXT);"
        )

    # edges need ir.t_connector
    if _table_exists("ir", "t_connector"):
        con.execute(HELPERS["port_edges"])
        con.execute(HELPERS["gen_edges"])
        con.execute(HELPERS["trace_edges"])
    else:
        con.execute(
            "CREATE OR REPLACE TABLE irx.port_edges (conn_oid BIGINT, src_port_oid BIGINT, dst_port_oid BIGINT, conn_type TEXT);"
        )
        con.execute(
            "CREATE OR REPLACE TABLE irx.gen_edges (child_oid BIGINT, parent_oid BIGINT);"
        )
        con.execute(
            "CREATE OR REPLACE TABLE irx.trace_edges (src_oid BIGINT, dst_oid BIGINT, kind TEXT);"
        )

    # Quick counts for logging/visibility.
    counts = {}
    for t in (
        "irx.blocks",
        "irx.ports",
        "irx.port_edges",
        "irx.gen_edges",
        "irx.trace_edges",
    ):
        counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    log.info(f"helpers: {counts}")
    return counts


def build_ir(model_dir: Path) -> Path:
    """End-to-end build: create `ir.*` views, `irx.*` helpers, then ANALYZE.

    Expect
    ------
    `<model_dir>/model.duckdb` must exist (produced by the loader).

    Output
    ------
    - `ir.*` views mirroring `main.t_*`
    - `irx.*` materialized helper tables in the same DB
    - Returns the DB path after closing the connection

    Notes
    -----
    - Runs `ANALYZE` to populate optimizer statistics.
    - Closes the connection before returning.
    """
    db_path = model_dir / "model.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB not found: {db_path}. Run loader first.")

    con = connect(db_path)
    created = create_ir_views(con)
    if not created:
        log.warning(
            "No base tables found to mirror into ir.* (did the loader create any t_* tables?)"
        )
    counts = build_helpers(con)
    con.execute("ANALYZE;")
    con.close()
    return db_path


def main():
    """CLI entrypoint: build IR for a given `--model-dir` and print the DB path."""
    ap = argparse.ArgumentParser("build-ir")
    ap.add_argument(
        "--model-dir",
        required=True,
        help="Directory containing model.duckdb (from loader)",
    )
    args = ap.parse_args()
    p = build_ir(Path(args.model_dir).resolve())
    print(str(p))


if __name__ == "__main__":
    main()
