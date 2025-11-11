# backend/app/ingest/discover_schema.py
# ------------------------------------------------------------
# Two-pass normalizer:
#   Pass 1: discover union of columns per <Table>.
#   Pass 2: stream rows and yield normalized dicts, filling
#           missing columns with defaults (or None).
# No CLI, no writers, no extras.
# ------------------------------------------------------------

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lxml.etree import iterparse

log = logging.getLogger("ingest.schema")


@contextmanager
def _timer(msg: str, **ctx: Any):
    """
    Lightweight timing context. Example:
      with _timer("discover-columns", xml=str(xml_path)): ...
    """
    t0 = time.perf_counter()
    if ctx:
        log.info("%s start %s", msg, ctx)
    else:
        log.info("%s start", msg)
    try:
        yield
    except Exception:
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


@dataclass(frozen=True)
class SchemaConfig:
    """
    Configures how to discover and read tables/rows/columns from arbitrary XML.
    - Tags are matched by *local-name* to be namespace-safe.
    - If your XML uses different tags/attrs, override the defaults.
    """

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
        if tag is None:
            return False
        # lxml elem.tag may be '{ns}local' or 'local'
        local = elem.tag.rsplit("}", 1)[-1]
        return local == tag


def _local(elem) -> str:
    """Namespace-agnostic tag local-name."""
    return elem.tag.rsplit("}", 1)[-1]


# Input: XML path; Output: {table -> sorted list of column names} for reproducible schemas.
# `include_extensions=True` treats <Extension .../> attributes as columns; disable to keep schemas tight.
# Stable sort ensures downstream code sees a deterministic column order.
def discover_columns(
    xml_path: str | Path,
    include_extensions: bool = True,
    config: SchemaConfig | None = None,
) -> dict[str, list[str]]:
    """
    Pass 1: Scan the XML and return deterministic column lists per table.

    Rules:
      - <Column name="..."> contributes its 'name'
      - <Extension .../> attributes contribute 'Extension_<attr>' (if enabled)
      - Columns are returned sorted A→Z for determinism
    """
    xml_path = str(Path(xml_path))
    cfg = config or SchemaConfig()
    cols: dict[str, set[str]] = defaultdict(set)
    current_table: str | None = None
    tables_seen = 0
    ext_cols = 0

    # Uses lxml.iterparse for streaming (does not load the whole XML into memory).
    # Pair with the cleanup block below to avoid memory growth on large files.
    with _timer(
        "discover-columns",
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
            tagname = elem.tag

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

    # deterministic order
    # Returns A→Z column lists so downstream view/table creation is repeatable across runs.
    schema = {t: sorted(list(names)) for t, names in cols.items()}
    log.info(
        "discovered schema tables=%d columns_total=%d extension_columns=%d",
        len(schema),
        sum(len(v) for v in schema.values()),
        ext_cols,
    )
    if tables_seen == 0:
        log.warning("no <%(tag)s> elements matched", {"tag": cfg.table_tag})
    return schema


# Returns (schema, row_iter): a schema dict and a single-use iterator of (table, row_dict).
# `defaults` fills missing columns per table; unspecified fields become None.
# Consumers must exhaust `row_iter` once (generator); materialize if you need multiple passes.
def normalized_rows(
    xml_path: str | Path,
    defaults: dict[str, dict[str, Any]] | None = None,
    include_extensions: bool = True,
    config: SchemaConfig | None = None,
) -> tuple[dict[str, list[str]], Iterable[tuple[str, dict[str, Any]]]]:
    """
    Two-pass stream normalizer.

    Returns:
      (schema, row_iter)
      - schema: {table: [col1, col2, ...]} discovered in Pass 1
      - row_iter: iterator of (table, normalized_row_dict) from Pass 2

    Parameters:
      defaults:
        Optional per-table, per-column defaults:
          {
            "t_package": {"Parent_ID": 0, "ModifiedDate": None, ...},
            "t_object":  {"Name": "", "Stereotype": None, ...}
          }
        If a (table, column) has no default specified, None is used.

      include_extensions:
        If True, treat <Extension .../> attributes as columns named "Extension_<attr>".
    """
    cfg = config or SchemaConfig()
    log.debug(
        "normalized_rows init xml='%s' include_extensions=%s defaults_provided=%s",
        str(xml_path),
        include_extensions,
        bool(defaults),
    )
    schema = discover_columns(
        xml_path, include_extensions=include_extensions, config=cfg
    )
    log.info("normalized_rows schema tables=%d", len(schema))

    def _row_stream() -> Iterable[tuple[str, dict[str, Any]]]:
        current_table: str | None = None
        current_row: dict[str, Any] | None = None
        rows_per_table: dict[str, int] = defaultdict(int)
        missing_fills_per_table: dict[str, int] = defaultdict(int)

        # Second streaming pass to yield normalized rows without building an in-memory DOM.
        # Memory cleanup below is essential for large XML files.
        with _timer("stream-rows", xml=str(xml_path)):
            for event, elem in iterparse(
                str(xml_path),
                events=("start", "end"),
                tag=None,
            ):
                tagname = _local(elem)

                if event == "start" and cfg.match(elem, cfg.table_tag):
                    tname = elem.get(cfg.table_name_attr)
                    # Only process tables we discovered (defensive)
                    current_table = tname if tname in schema else None
                    if tname and current_table is None:
                        log.debug(
                            "skipping unknown table name='%s' (not in discovered schema)",
                            tname,
                        )

                elif (
                    event == "start" and cfg.match(elem, cfg.row_tag) and current_table
                ):
                    current_row = {}

                # Prefer <Column value="...">; fallback to element text if value is absent.
                # Empty strings are normalized to None—downstream code should handle nulls.
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
                # Adds "Extension_<attr>" fields to the current row so shapes match the discovered schema.
                # Keep `include_extensions` consistent with Pass 1, or shapes will diverge.
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

                # Ensures every emitted row has all schema columns: use per-table defaults, else None.
                # Invariant: output rows are schema-complete; types may widen to nullable because of None.
                elif (
                    event == "end"
                    and cfg.match(elem, cfg.row_tag)
                    and current_table
                    and current_row is not None
                ):
                    # Fill missing columns with defaults (or None)
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

                # memory cleanup
                # Frees parsed nodes promptly (clear + unlink siblings) to keep memory flat during streaming.
                # Do not keep references to `elem`/parents elsewhere, or cleanup won’t reclaim memory.
                if event == "end":
                    parent = elem.getparent() if hasattr(elem, "getparent") else None
                    elem.clear()
                    if parent is not None:
                        while elem.getprevious() is not None:
                            del parent[0]
        # end with _timer
        log.info(
            "stream summary rows_per_table=%s missing_fills=%s",
            {t: rows_per_table[t] for t in sorted(rows_per_table)},
            {t: missing_fills_per_table[t] for t in sorted(missing_fills_per_table)},
        )

    # Fail fast if we found no tables/columns; better than silently yielding nothing
    if not schema:
        raise ValueError(
            "No tables/columns discovered. Check SchemaConfig or XML structure."
        )
    return schema, _row_stream()
