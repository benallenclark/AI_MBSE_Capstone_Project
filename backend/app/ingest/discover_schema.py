# ------------------------------------------------------------
# Module: backend/app/ingest/discover_schema.py
# Purpose: Stream an XML file and derive a deterministic {table: [columns]} schema.
# ------------------------------------------------------------

"""Schema discovery from XML for reproducible downstream processing.

This module parses large XML files in a streaming fashion and extracts a stable,
deterministic mapping of table names to sorted column lists.

Responsibilities
----------------
- Parse XML with `lxml.iterparse` without loading the entire file into memory.
- Detect tables, columns, and optional extension attributes as columns.
- Return columns sorted A→Z for deterministic schemas across runs.
- Emit structured timing and progress logs for observability.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from lxml.etree import iterparse

from app.ingest.schema_config import SchemaConfig
from app.utils.timing import log_timer

log = logging.getLogger("ingest.schema")


def discover_columns(
    xml_path: str | Path,
    include_extensions: bool = True,
    config: SchemaConfig | None = None,
) -> dict[str, list[str]]:
    """
    Parse an XML file and return {table: [columns]}.

    Rules
    -----
    - `<Column name="...">` adds its name.
    - `<Extension .../>` adds prefixed attributes (if enabled).
    - Columns are sorted alphabetically for determinism.
    """
    xml_path = str(Path(xml_path))
    cfg = config or SchemaConfig()
    cols: dict[str, set[str]] = defaultdict(set)
    current_table: str | None = None
    tables_seen = 0
    ext_cols = 0

    # Stream parsing avoids loading entire XML into memory.
    with log_timer(
        "discover-columns",
        logger=log,
        xml=xml_path,
        include_extensions=include_extensions,
        table_tag=cfg.table_tag,
        row_tag=cfg.row_tag,
        column_tag=cfg.column_tag,
        extension_tag=cfg.extension_tag,
    ):
        for event, elem in iterparse(
            xml_path,
            events=("start", "end"),
            tag=None,  # match all; we will filter by local-name to be namespace-safe
        ):
            if event == "start" and cfg.match(elem, cfg.table_tag):
                current_table = elem.get(cfg.table_name_attr)
                if not current_table:
                    log.warning(
                        "table without '%s' attribute encountered", cfg.table_name_attr
                    )
                else:
                    tables_seen += 1

            elif event == "start" and cfg.match(elem, cfg.column_tag) and current_table:
                name = elem.get(cfg.column_name_attr)
                if name:
                    cols[current_table].add(name)
                else:
                    log.warning(
                        "column without '%s' attribute in table '%s'",
                        cfg.column_name_attr,
                        current_table,
                    )

            # Each attribute becomes a namespaced column "Extension_<attr>" to avoid collisions.
            # Very heterogeneous extensions can explode column count—consider disabling if not needed.
            elif (
                include_extensions
                and cfg.extension_tag
                and event == "start"
                and cfg.match(elem, cfg.extension_tag)
                and current_table
            ):
                for k in elem.keys():
                    cols[current_table].add(f"{cfg.extension_prefix}{k}")
                    ext_cols += 1

            elif event == "end" and cfg.match(elem, cfg.table_tag):
                current_table = None

            # memory cleanup
            if event == "end":
                parent = elem.getparent() if hasattr(elem, "getparent") else None
                elem.clear()
                if parent is not None:
                    while elem.getprevious() is not None:
                        del parent[0]

    # Return sorted column lists for repeatability.
    schema = {t: sorted(names) for t, names in cols.items()}
    log.info(
        "discovered schema tables=%d columns_total=%d extension_columns=%d",
        len(schema),
        sum(len(v) for v in schema.values()),
        ext_cols,
    )
    if tables_seen == 0:
        log.warning("no <%(tag)s> elements matched", {"tag": cfg.table_tag})
    return schema
