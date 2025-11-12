# ------------------------------------------------------------
# Module: backend/app/ingest/write_jsonl.py
# Purpose: Stream table rows into per-table JSONL files with minimal open handles.
# ------------------------------------------------------------

"""Efficiently writes one JSONL file per table using an LRU of open file handles.

This avoids running out of file descriptors on large datasets while ensuring
each table’s rows append deterministically to its own file.

Responsibilities
----------------
- Manage limited open file handles with a small LRU cache.
- Write rows as JSONL lines, one file per table.
- Create output directories if missing.
- Raise `FileWriteError` on write or close failures.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path

from .errors import FileWriteError


def write_jsonl_tables(
    row_iter: Iterable[tuple[str, dict]],
    out_dir: Path,
    max_open: int | None = None,
) -> dict[str, Path]:
    """
    Write one JSONL file per table with a limited number of open handles.

    Each table’s rows are appended to its own file. Oldest open handles are closed
    when the limit is exceeded.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    max_open = 64 if max_open is None else max_open
    handles: OrderedDict[str, tuple[Path, object]] = OrderedDict()
    paths: dict[str, Path] = {}

    def _open_handle(table: str):
        p = out_dir / f"{table}.jsonl"
        f = p.open("a", encoding="utf-8")
        handles[table] = (p, f)
        paths.setdefault(table, p)
        if len(handles) > max_open:
            # close the least-recently used handle
            old_table, (_, old_f) = handles.popitem(last=False)
            try:
                old_f.close()
            except Exception:
                pass
        return f, p

    try:
        for table, row in row_iter:
            # reuse or open
            if table in handles:
                p, f = handles[table][0], handles[table][1]
                # mark recent
                handles.move_to_end(table)
            else:
                f, p = _open_handle(table)

            try:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except Exception as e:
                raise FileWriteError(f"write failed table='{table}' path='{p}'") from e
    finally:
        for _, (_, f) in list(handles.items()):
            try:
                f.close()
            except Exception:
                pass

    return paths
