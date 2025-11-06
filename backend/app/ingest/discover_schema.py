# backend/app/ingest/discover_schema.py
# ------------------------------------------------------------
# Two-pass normalizer:
#   Pass 1: discover union of columns per <Table>.
#   Pass 2: stream rows and yield normalized dicts, filling
#           missing columns with defaults (or None).
# No CLI, no writers, no extras.
# ------------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from lxml.etree import iterparse
from collections import defaultdict
from typing import Dict, List, Set, Optional, Iterable, Tuple, Any

# Input: XML path; Output: {table -> sorted list of column names} for reproducible schemas.
# `include_extensions=True` treats <Extension .../> attributes as columns; disable to keep schemas tight.
# Stable sort ensures downstream code sees a deterministic column order.
def discover_columns(
    xml_path: str | Path,
    include_extensions: bool = True,
) -> Dict[str, List[str]]:
    """
    Pass 1: Scan the XML and return deterministic column lists per table.

    Rules:
      - <Column name="..."> contributes its 'name'
      - <Extension .../> attributes contribute 'Extension_<attr>' (if enabled)
      - Columns are returned sorted A→Z for determinism
    """
    xml_path = str(Path(xml_path))
    cols: Dict[str, Set[str]] = defaultdict(set)
    current_table: Optional[str] = None

    # Uses lxml.iterparse for streaming (does not load the whole XML into memory).
    # Pair with the cleanup block below to avoid memory growth on large files.
    for event, elem in iterparse(
        xml_path,
        events=("start", "end"),
        tag=("Table", "Row", "Column", "Extension"),
    ):
        tagname = elem.tag

        if event == "start" and tagname == "Table":
            current_table = elem.get("name")

        elif event == "start" and tagname == "Column" and current_table:
            name = elem.get("name")
            if name:
                cols[current_table].add(name)
        
        # Each attribute becomes a namespaced column "Extension_<attr>" to avoid collisions.
        # Very heterogeneous extensions can explode column count—consider disabling if not needed.
        elif include_extensions and event == "start" and tagname == "Extension" and current_table:
            for k in elem.keys():
                cols[current_table].add(f"Extension_{k}")

        elif event == "end" and tagname == "Table":
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
    return {t: sorted(list(names)) for t, names in cols.items()}

# Returns (schema, row_iter): a schema dict and a single-use iterator of (table, row_dict).
# `defaults` fills missing columns per table; unspecified fields become None.
# Consumers must exhaust `row_iter` once (generator); materialize if you need multiple passes.
def normalized_rows(
    xml_path: str | Path,
    defaults: Optional[Dict[str, Dict[str, Any]]] = None,
    include_extensions: bool = True,
) -> Tuple[Dict[str, List[str]], Iterable[Tuple[str, Dict[str, Any]]]]:
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
    schema = discover_columns(xml_path, include_extensions=include_extensions)

    def _row_stream() -> Iterable[Tuple[str, Dict[str, Any]]]:
        current_table: Optional[str] = None
        current_row: Optional[Dict[str, Any]] = None

        # Second streaming pass to yield normalized rows without building an in-memory DOM.
        # Memory cleanup below is essential for large XML files.
        for event, elem in iterparse(
            str(xml_path),
            events=("start", "end"),
            tag=("Table", "Row", "Column", "Extension"),
        ):
            tagname = elem.tag

            if event == "start" and tagname == "Table":
                tname = elem.get("name")
                # Only process tables we discovered (defensive)
                current_table = tname if tname in schema else None

            elif event == "start" and tagname == "Row" and current_table:
                current_row = {}

            # Prefer <Column value="...">; fallback to element text if value is absent.
            # Empty strings are normalized to None—downstream code should handle nulls.
            elif event == "end" and tagname == "Column" and current_table and current_row is not None:
                col = elem.get("name")
                if col:
                    val = elem.get("value")
                    if val is None:
                        txt = (elem.text or "").strip()
                        val = txt if txt != "" else None
                    current_row[col] = val
            
            # Adds "Extension_<attr>" fields to the current row so shapes match the discovered schema.
            # Keep `include_extensions` consistent with Pass 1, or shapes will diverge.
            elif include_extensions and event == "start" and tagname == "Extension" and current_table and current_row is not None:
                for k, v in elem.items():
                    current_row[f"Extension_{k}"] = v
            
            # Ensures every emitted row has all schema columns: use per-table defaults, else None.
            # Invariant: output rows are schema-complete; types may widen to nullable because of None.
            elif event == "end" and tagname == "Row" and current_table and current_row is not None:
                # Fill missing columns with defaults (or None)
                table_defaults = (defaults or {}).get(current_table, {})
                filled = {col: current_row.get(col, table_defaults.get(col, None)) for col in schema[current_table]}
                yield (current_table, filled)
                current_row = None

            elif event == "end" and tagname == "Table":
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

    return schema, _row_stream()
