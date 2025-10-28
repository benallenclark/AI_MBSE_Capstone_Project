# ------------------------------------------------------------
# Module: app/input_adapters/protocols.py
# Purpose: Define the standard interface for vendor-specific model adapters.
# ------------------------------------------------------------

"""Protocol definitions for model input adapters.

Summary:
    Defines the common interface that all vendor-specific model adapters
    must implement to integrate with the MBSE Maturity analysis pipeline.

Details:
    - Each adapter converts a vendor’s native model export
      (e.g., Sparx Enterprise Architect XML, Cameo `.mdxml`)
      into a temporary, standardized data store such as an in-memory SQLite database.
    - The analysis engine executes SQL-based predicates on this database
      to determine model maturity and produce evidence for higher-level reporting.

Developer Guidance:
    - Each adapter must implement the `Adapter` protocol below.
    - Keep the interface minimal to avoid coupling and vendor-specific logic.
    - Always return a live `sqlite3.Connection` that callers can close safely.
    - Handle XML parsing and schema mapping entirely inside the adapter.
    - Never import or depend on FastAPI modules—this layer must remain backend-agnostic.
"""

from typing import Protocol
import sqlite3


class Adapter(Protocol):
    """Interface for vendor-specific model adapters.

    Methods:
        build_db(xml_bytes: bytes) -> sqlite3.Connection:
            Parse the given XML byte stream and return a ready-to-query
            SQLite connection containing the model’s extracted tables.

    Example:
        class Sparx171(Adapter):
            def build_db(self, xml_bytes: bytes) -> sqlite3.Connection:
                # Parse native Sparx XML
                # Populate temp SQLite DB with t_object, t_connector, etc.
                return connection
    """

    def build_db(self, xml_bytes: bytes) -> sqlite3.Connection:
        """Convert XML bytes into an in-memory SQLite database.

        Args:
            xml_bytes (bytes): The raw XML data from a model export.

        Returns:
            sqlite3.Connection: Live SQLite connection with parsed model data.

        Raises:
            ValueError: If parsing or database population fails.
        """
        ...
