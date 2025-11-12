# ------------------------------------------------------------
# Module: backend/app/ingest/schema_config.py
# Purpose: Define XML schema configuration for table/row/column discovery.
# ------------------------------------------------------------

"""Configuration model for parsing XML into tabular structures.

Provides a namespace-agnostic way to match XML elements representing
tables, rows, and columns for ingestion workflows.

Responsibilities
----------------
- Define tag and attribute names for tables, rows, and columns.
- Support optional extension elements that add dynamic columns.
- Offer namespace-agnostic tag matching using local-name extraction.
- Serve as a configuration object for XML schema discovery logic.
"""

from __future__ import annotations

from dataclasses import dataclass


def local_name(elem) -> str:
    """Return the namespace-agnostic local name of an XML tag."""
    return elem.tag.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class SchemaConfig:
    """Configuration for discovering tables, rows, and columns in XML."""

    table_tag: str = "Table"
    table_name_attr: str = "name"
    row_tag: str = "Row"
    column_tag: str = "Column"
    column_name_attr: str = "name"
    column_value_attr: str = "value"
    # Optional "extensions" element whose attributes become columns on the table/row
    extension_tag: str | None = "Extension"
    extension_prefix: str = "Extension_"

    def match(self, elem, tag: str | None) -> bool:
        """Return True if the element matches the given local-name tag."""
        if tag is None:
            return False
        return local_name(elem) == tag
