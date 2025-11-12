# ------------------------------------------------------------
# Module: backend/app/ingest/normalize_rows.py
# Purpose: Stream-normalize XML into tabular rows based on a discovered schema.
# ------------------------------------------------------------

"""Normalize XML into table-shaped rows via a two-pass process.

The module discovers a schema from the XML, then streams the document to yield
(table, row) pairs with defaults and extensions applied.

Responsibilities
----------------
- Discover table/column schema from XML using `SchemaConfig`.
- Stream-parse XML elements and match table/row/column tags.
- Apply per-table defaults and extension attributes; fill missing columns.
- Yield normalized (table, row) tuples and return the discovered schema.
- Log timing and a summary of rows and missing fills.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lxml.etree import iterparse

from app.flow.ingest.discover_schema import discover_columns
from app.flow.ingest.schema_config import SchemaConfig, local_name
from app.infra.utils.timing import log_timer

log = logging.getLogger("ingest.normalize")


def normalized_rows(
    xml_path: str | Path,
    defaults: dict[str, dict[str, Any]] | None = None,
    include_extensions: bool = True,
    config: SchemaConfig | None = None,
) -> tuple[dict[str, list[str]], Iterable[tuple[str, dict[str, Any]]]]:
    """
    Two-pass stream normalizer.
    Returns (schema, row_iter) where row_iter yields (table, normalized_row_dict).
    """
    cfg = config or SchemaConfig()
    schema = discover_columns(
        xml_path, include_extensions=include_extensions, config=cfg
    )
    if not schema:
        raise ValueError(
            "No tables/columns discovered. Check SchemaConfig or XML structure."
        )
    log.info("normalized_rows schema tables=%d", len(schema))

    def _row_stream() -> Iterable[tuple[str, dict[str, Any]]]:
        current_table: str | None = None
        current_row: dict[str, Any] | None = None
        rows_per_table: dict[str, int] = defaultdict(int)
        missing_fills_per_table: dict[str, int] = defaultdict(int)

        with log_timer("stream-rows", xml=str(xml_path)):
            for event, elem in iterparse(
                str(xml_path), events=("start", "end"), tag=None
            ):
                tag = local_name(elem)

                if event == "start" and cfg.match(elem, cfg.table_tag):
                    tname = elem.get(cfg.table_name_attr)
                    current_table = tname if (tname in schema) else None
                    if tname and current_table is None:
                        log.debug(
                            "skip unknown table name='%s' (not in discovered schema)",
                            tname,
                        )

                elif (
                    event == "start" and cfg.match(elem, cfg.row_tag) and current_table
                ):
                    current_row = {}

                elif (
                    event == "end"
                    and cfg.match(elem, cfg.column_tag)
                    and current_table
                    and current_row is not None
                ):
                    col = elem.get(cfg.column_name_attr)
                    if col:
                        val = elem.get(cfg.column_value_attr)
                        if val is None:
                            txt = (elem.text or "").strip()
                            val = txt if txt != "" else None
                        current_row[col] = val
                    else:
                        log.warning(
                            "row column missing '%s' attribute table='%s'",
                            cfg.column_name_attr,
                            current_table,
                        )

                elif (
                    include_extensions
                    and cfg.extension_tag
                    and event == "start"
                    and cfg.match(elem, cfg.extension_tag)
                    and current_table
                    and current_row is not None
                ):
                    for k, v in elem.items():
                        current_row[f"{cfg.extension_prefix}{k}"] = v

                elif (
                    event == "end"
                    and cfg.match(elem, cfg.row_tag)
                    and current_table
                    and current_row is not None
                ):
                    table_defaults = (defaults or {}).get(current_table, {})
                    filled = {}
                    missing = 0
                    for col in schema[current_table]:
                        if col in current_row:
                            filled[col] = current_row[col]
                        else:
                            filled[col] = table_defaults.get(col, None)
                            missing += 1
                    if missing:
                        missing_fills_per_table[current_table] += missing
                    rows_per_table[current_table] += 1
                    yield (current_table, filled)
                    current_row = None

                elif event == "end" and cfg.match(elem, cfg.table_tag):
                    current_table = None

                # Memory cleanup on 'end' to keep streaming footprint low.
                if event == "end":
                    parent = elem.getparent() if hasattr(elem, "getparent") else None
                    elem.clear()
                    if parent is not None:
                        while elem.getprevious() is not None:
                            del parent[0]

        log.info(
            "stream summary rows_per_table=%s missing_fills=%s",
            {t: rows_per_table[t] for t in sorted(rows_per_table)},
            {t: missing_fills_per_table[t] for t in sorted(missing_fills_per_table)},
        )

    return schema, _row_stream()
