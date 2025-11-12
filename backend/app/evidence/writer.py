# ---------------------------------------------------------------------
# backend/app/evidence/writer.py — Evidence v2 only
# Purpose: Single, canonical entrypoints for emitting Evidence v2 cards.
# ---------------------------------------------------------------------

"""Emit and manage Evidence v2 card files on disk.

Responsibilities
----------------
- Write Evidence v2 cards to `<model_dir>/evidence` as JSONL.
- Support batch emission for multiple predicates efficiently.
- Optionally mirror the JSONL data to Parquet for analytics.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterable
from typing import Any

import duckdb

from .builder import EvidenceBuilder
from .types import PredicateOutput


def emit_evidence(
    model_dir: pathlib.Path, ctx: dict[str, Any], output: PredicateOutput
) -> list[dict[str, Any]]:
    """Emit Evidence v2 cards for a single predicate.

    Notes
    -----
    - Writes JSONL cards under `<model_dir>/evidence`.
    - Returns emitted card dicts so callers can inspect or log them.
    - May raise if `output` is malformed or directory setup fails.
    """
    # Create a one-time builder tied to `model_dir` (handles layout and append logic).
    return EvidenceBuilder(model_dir).emit(ctx, output)


def emit_batch(
    model_dir: pathlib.Path, ctx: dict[str, Any], outputs: Iterable[PredicateOutput]
) -> list[dict[str, Any]]:
    """Emit multiple Evidence v2 predicate outputs in sequence.

    Notes
    -----
    - Uses a single builder for efficiency (no per-call setup).
    - Preserves iteration order for stable logs and snapshots.
    - Returns a flat list of all emitted card dicts.
    """
    builder = EvidenceBuilder(model_dir)
    docs: list[dict[str, Any]] = []

    for out in outputs:
        docs.extend(builder.emit(ctx, out))
    return docs


def mirror_jsonl_to_parquet(model_dir: pathlib.Path) -> pathlib.Path:
    """Create a Parquet mirror of `evidence.jsonl` for faster analytics.

    Notes
    -----
    - Must be run after all emits are complete (not incremental).
    - Overwrites any existing Parquet file of the same name.
    - Returns the path to the created Parquet file.
    """

    ev_dir = model_dir / "evidence"
    src = (ev_dir / "evidence.jsonl").as_posix()
    dst = (ev_dir / f"{model_dir.name}_evidence.parquet").as_posix()

    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_json_auto('{src}')) TO '{dst}' (FORMAT PARQUET);"
    )
    con.close()

    return pathlib.Path(dst)
