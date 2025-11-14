# ------------------------------------------------------------
# Module: app/knowledge/criteria/mml_2/predicate_block_has_port.py
# Purpose: MML-2 — every Block has ≥1 Port, emit full evidence per block
# Evidence v2: predicates return a small typed output; builder writes cards
# ------------------------------------------------------------
from __future__ import annotations

from typing import Any

from app.knowledge.criteria.protocols import Context, DbLike
from app.knowledge.criteria.utils import predicate


# ---------- column helpers (adapter-agnostic) ----------
def _cols(db: DbLike, table: str) -> dict[str, str]:
    # Map lowercased name -> actual case
    cur = db.execute(f"PRAGMA table_info({table})")
    return {str(r[1]).lower(): str(r[1]) for r in cur.fetchall()}


def _pick(present: dict[str, str], *candidates: str) -> str:
    for c in candidates:
        if c.lower() in present:
            return present[c.lower()]
    raise KeyError(f"none of {candidates} found in {list(present.keys())}")


# ---------- predicate ----------
def _core(db: DbLike, ctx: Context) -> dict[str, Any]:
    c_obj = _cols(db, "t_object")

    OBJECT_ID = _pick(c_obj, "Object_ID", "object_id", "id")
    OBJECT_TYPE = _pick(c_obj, "Object_Type", "object_type", "type")
    NAME = _pick(c_obj, "Name", "name")
    PARENT_ID = _pick(c_obj, "ParentID", "parentid", "parent_id")
    STEREO = _pick(c_obj, "Stereotype", "stereotype")
    EA_GUID_COL = c_obj.get("ea_guid", "")  # optional (Sparx)

    # Build SQL once; DuckDB-friendly (uses COALESCE) and portable
    if EA_GUID_COL:
        sql = f"""
        SELECT
          b."{OBJECT_ID}"              AS block_id,
          b."{EA_GUID_COL}"            AS block_guid,
          b."{NAME}"                   AS block_name,
          p."{OBJECT_ID}"              AS port_id,
          p."{EA_GUID_COL}"            AS port_guid,
          p."{NAME}"                   AS port_name,
          p."{STEREO}"                 AS port_stereotype
        FROM t_object b
        LEFT JOIN t_object p
          ON p."{PARENT_ID}" = b."{OBJECT_ID}" AND p."{OBJECT_TYPE}"='Port'
        WHERE b."{OBJECT_TYPE}"='Class'
          AND LOWER(COALESCE(b."{STEREO}",''))='block'
        ORDER BY LOWER(b."{NAME}"), LOWER(COALESCE(p."{NAME}",'')), b."{OBJECT_ID}", p."{OBJECT_ID}";
        """
    else:
        sql = f"""
        SELECT
          b."{OBJECT_ID}"              AS block_id,
          CAST(NULL AS VARCHAR)        AS block_guid,
          b."{NAME}"                   AS block_name,
          p."{OBJECT_ID}"              AS port_id,
          CAST(NULL AS VARCHAR)        AS port_guid,
          p."{NAME}"                   AS port_name,
          p."{STEREO}"                 AS port_stereotype
        FROM t_object b
        LEFT JOIN t_object p
          ON p."{PARENT_ID}" = b."{OBJECT_ID}" AND p."{OBJECT_TYPE}"='Port'
        WHERE b."{OBJECT_TYPE}"='Class'
          AND LOWER(COALESCE(b."{STEREO}",''))='block'
        ORDER BY LOWER(b."{NAME}"), LOWER(COALESCE(p."{NAME}",'')), b."{OBJECT_ID}", p."{OBJECT_ID}";
        """

    rows = db.execute(sql).fetchall()

    # Group ports per block
    by_block: dict[int, dict[str, Any]] = {}
    for (
        block_id,
        block_guid,
        block_name,
        port_id,
        port_guid,
        port_name,
        port_stereo,
    ) in rows:
        b = by_block.get(block_id)
        if b is None:
            b = {
                "block_id": int(block_id),
                "block_guid": (block_guid or "") if block_guid is not None else "",
                "block_name": str(block_name),
                "ports": [],
            }
            by_block[block_id] = b
        if port_id is not None:
            b["ports"].append(
                {
                    "port_id": int(port_id),
                    "port_guid": (port_guid or "") if port_guid is not None else "",
                    "port_name": str(port_name) if port_name is not None else "",
                    "port_stereotype": str(port_stereo)
                    if port_stereo is not None
                    else "",
                }
            )

    blocks_total = len(by_block)
    blocks_with_ports = sum(1 for b in by_block.values() if len(b["ports"]) > 0)
    blocks_missing_ports = blocks_total - blocks_with_ports
    passed = blocks_missing_ports == 0

    # Coverage ratio: how many blocks actually expose ports?
    ratio = (blocks_with_ports / blocks_total) if blocks_total else 0.0

    # Build facts: one per block (decorator will emit evidence)
    facts: list[dict[str, Any]] = []
    for b in sorted(
        by_block.values(), key=lambda x: (x["block_name"].lower(), x["block_id"])
    ):
        has_ports = len(b["ports"]) > 0
        facts.append(
            {
                "subject_type": "block",
                "subject_id": str(b["block_id"]),
                "subject_name": b["block_name"],
                "tags": ["block", "port"] + ([] if has_ports else ["missing"]),
                "child_count": len(b["ports"]),
                "has_issue": (not has_ports),
                "meta": {
                    "block_guid": b["block_guid"],
                    # Keep full port list in meta for provenance; retrieval can downselect.
                    "ports": b["ports"],
                },
            }
        )

    counts = {
        "blocks_total": blocks_total,
        "with_ports": blocks_with_ports,
        "missing_ports": blocks_missing_ports,
    }

    # Universal summary for UI: ok/total
    measure = {
        "ok": blocks_with_ports,
        "total": blocks_total,
    }

    # Minimal return; decorator infers mml/probe_id and emits evidence
    return {
        "passed": passed,
        "counts": counts,
        "measure": measure,
        "facts": facts,
        "source_tables": ["t_object"],
        "domain": "Interface Definition",
        "severity": (
            "high"
            if blocks_total and ratio < 0.5
            else "medium"
            if blocks_total and ratio < 0.8
            else "low"
        ),
    }


# Export evaluate that the loader expects
evaluate = predicate(_core)
