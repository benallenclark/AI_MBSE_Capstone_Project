# ------------------------------------------------------------
# Module: app/input_adapters/sparx/v17_1/adapter.py
# Purpose: Implement the Sparx Enterprise Architect v17.1 adapter for model ingestion.
# ------------------------------------------------------------

"""Sparx Enterprise Architect v17.1 adapter.

Summary:
    Converts Sparx Enterprise Architect native XML exports (v17.1)
    into an in-memory SQLite database that mirrors key `t_*` tables
    (e.g., `t_object`, `t_connector`, `t_package`, etc.).

Details:
    - Used by the `/v1/analyze` API route through the adapter router.
    - Provides a temporary, read-only SQLite database for deterministic
      maturity predicates to query.
    - Replaces the deprecated Graph-IR pipeline with SQL-backed checks.

Developer Guidance:
    - Keep parsing logic minimal—delegate XML → SQLite conversion to
      `app.tempdb.loader.load_xml_to_mem`.
    - Maintain statelessness: the adapter should only transform bytes into a
      ready-to-query in-memory schema.
    - The returned `sqlite3.Connection` must always be closed by the caller.
    - Avoid introducing vendor-specific hacks here; handle quirks in upstream adapters.
    - Do not implement deprecated `Graph-IR` functionality—use SQL predicates only.
"""

from __future__ import annotations

import sqlite3
from app.input_adapters.protocols import Adapter
from app.tempdb.loader import load_xml_to_mem  # Converts XML bytes → sqlite3.Connection


class Sparx171(Adapter):
    """Adapter for Sparx Enterprise Architect v17.1 models.

    Responsibilities:
        - Parse the native Sparx XML export.
        - Load its tables (`t_object`, `t_connector`, etc.) into
          a temporary in-memory SQLite database.
        - Return a live `sqlite3.Connection` ready for predicate queries.

    Notes:
        - No files are written to disk; everything stays in RAM.
        - This ensures high throughput and zero persistence risk.
    """

    def build_db(self, xml_bytes: bytes) -> sqlite3.Connection:
        """Convert Sparx v17.1 native XML bytes into an in-memory SQLite DB.

        Args:
            xml_bytes (bytes): The raw XML export from Sparx Enterprise Architect.

        Returns:
            sqlite3.Connection: Connection to the populated temporary database.

        Raises:
            ValueError: If XML parsing or schema population fails.

        Example:
            >>> adapter = Sparx171()
            >>> conn = adapter.build_db(xml_bytes)
            >>> rows = conn.execute('SELECT COUNT(*) FROM t_object').fetchone()
        """
        # Parse XML and materialize t_* tables entirely in RAM
        return load_xml_to_mem(xml_bytes)
