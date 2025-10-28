"""Test: verify that the XML→SQLite loader builds a valid in-memory database.

Purpose:
    Ensures `load_xml_to_mem` parses a vendor XML export (sample input)
    and materializes the expected MBSE tables in an in-memory SQLite DB.

Why:
    This confirms the ingestion pipeline works end-to-end without disk I/O.
    If this test fails, the parser or schema detection logic is broken.

How it works:
    - Call the loader on `sample_xml_bytes` (pytest fixture provides small XML sample)
    - Query sqlite_schema to confirm core tables were created
    - Verify row counts match known values from the sample XML
"""

from app.tempdb.loader import load_xml_to_mem

def test_loader_builds_in_memory_db(sample_xml_bytes):
    # Build an in-memory SQLite database from sample XML bytes
    db = load_xml_to_mem(sample_xml_bytes)
    try:
        # Collect all created table names
        tables = {
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
            ).fetchall()
        }

        # Basic existence checks: loader should create these tables
        assert "t_object" in tables
        assert "t_package" in tables

        # Verify expected row counts match the known XML fixture data
        n_obj = db.execute("SELECT COUNT(*) FROM t_object").fetchone()[0]
        n_pkg = db.execute("SELECT COUNT(*) FROM t_package").fetchone()[0]
        assert n_obj == 2      # fixture has two <t_object> rows
        assert n_pkg == 1      # fixture has one <t_package> row
    finally:
        db.close()  # Always close in-memory DB to free resources
