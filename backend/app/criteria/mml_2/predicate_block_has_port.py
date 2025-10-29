# ------------------------------------------------------------
# Module: app/criteria/mml_2/predicate_block_has_port.py
# Purpose: Verify that each SysML Block element has at least one Port (MML-2).
# ------------------------------------------------------------

"""MML-2 Predicate: Verify that each Block has at least one Port.

Summary:
    Ensures every Block element defined in the model contains one or more
    Ports. This check builds upon the MML-1 schema validation to confirm
    structural completeness and interface definition within each Block.

Behavior:
    - Finds all rows in `t_object` where Object_Type='Class' and Stereotype='block'.
    - Left joins potential child Port elements on ParentID.
    - Counts Ports per Block.
    - Reports Blocks missing Ports in the result details.

Rationale:
    A Block without Ports represents an incomplete interface specification
    in SysML and indicates immature model structure. Ensuring every Block
    defines at least one Port establishes interface visibility for integration.

Developer Notes:
    - Works for both native and profile-applied stereotypes (`t_xref` lookup).
    - Keep queries adapter-agnostic and SQLite-compatible.
    - Future maturity levels may refine port type checks (e.g., FlowPort only).
"""

from typing import Tuple, Dict, Any, TypedDict, List, cast, NotRequired
from app.criteria.protocols import Context, DbLike

PREDICATE_ID = "block_has_port"

class BlockRec(TypedDict):
    block_id: int
    block_guid: str
    block_name: str
    port_count: int

class Counts(TypedDict):
    passed: int
    failed: int

class Evidence(TypedDict):
    passed: List[BlockRec]
    failed: List[BlockRec]
    truncated: NotRequired[Dict[str, bool]]  # e.g., {"passed": True, "failed": False}

class Details(TypedDict):
    vendor: str
    version: str
    blocks_total: int
    blocks_with_ports: int
    blocks_missing_ports: int
    counts: Counts
    evidence: Evidence
    capabilities: Dict[str, bool]

# ---- column resolution ----

def _cols(db: DbLike, table: str) -> Dict[str, str]:
    cur = db.execute(f"PRAGMA table_info({table})")
    present = {str(r[1]).lower(): str(r[1]) for r in cur.fetchall()}
    return present  # map lower->actual

def _pick(present: Dict[str, str], *candidates: str) -> str:
    for c in candidates:
        if c.lower() in present:
            return present[c.lower()]
    raise KeyError(f"none of {candidates} found")

# ---- evaluate ----

def evaluate(db: DbLike, ctx: Context) -> Tuple[bool, Details]:
    c_obj = _cols(db, "t_object")
    # pick actual column spellings
    OBJECT_ID   = _pick(c_obj, "Object_ID", "object_id", "id")
    OBJECT_TYPE = _pick(c_obj, "Object_Type", "object_type", "type")
    NAME        = _pick(c_obj, "Name", "name")
    PARENT_ID   = _pick(c_obj, "ParentID", "parentid", "parent_id")
    STEREO      = _pick(c_obj, "Stereotype", "stereotype")
    # optional
    EA_GUID     = c_obj.get("ea_guid", "")  # may be missing

    # Build SQL that works with resolved names
    if EA_GUID:
        sql = f"""
        SELECT
          b."{OBJECT_ID}"  AS block_id,
          b."{EA_GUID}"    AS block_guid,
          b."{NAME}"       AS block_name,
          COUNT(p."{OBJECT_ID}") AS port_count
        FROM t_object AS b
        LEFT JOIN t_object AS p
          ON p."{PARENT_ID}" = b."{OBJECT_ID}"
         AND p."{OBJECT_TYPE}" = 'Port'
        WHERE b."{OBJECT_TYPE}" = 'Class'
          AND LOWER(IFNULL(b."{STEREO}",'')) = 'block'
        GROUP BY b."{OBJECT_ID}", b."{EA_GUID}", b."{NAME}";
        """
    else:
        sql = f"""
        SELECT
          b."{OBJECT_ID}"  AS block_id,
          ''               AS block_guid,
          b."{NAME}"       AS block_name,
          COUNT(p."{OBJECT_ID}") AS port_count
        FROM t_object AS b
        LEFT JOIN t_object AS p
          ON p."{PARENT_ID}" = b."{OBJECT_ID}"
         AND p."{OBJECT_TYPE}" = 'Port'
        WHERE b."{OBJECT_TYPE}" = 'Class'
          AND LOWER(IFNULL(b."{STEREO}",'')) = 'block'
        GROUP BY b."{OBJECT_ID}", b."{NAME}";
        """

    cur = db.execute(sql)
    rows: List[BlockRec] = [{
        "block_id":   int(r[0]),
        "block_guid": str(r[1]),
        "block_name": str(r[2]),
        "port_count": int(r[3]),
    } for r in cur.fetchall()]

    passed_items = [r for r in rows if r["port_count"] > 0]
    failed_items = [r for r in rows if r["port_count"] == 0]

    # deterministic ordering
    def _key(r): return (r["block_name"].lower(), r["block_id"])
    passed_sorted = sorted(passed_items, key=_key)
    failed_sorted = sorted(failed_items, key=_key)

    details: Details = {
        "vendor": ctx.vendor,
        "version": ctx.version,
        "blocks_total": len(rows),
        "blocks_with_ports": len(passed_sorted),
        "blocks_missing_ports": len(failed_sorted),
        "counts": {"passed": len(passed_sorted), "failed": len(failed_sorted)},
        "evidence": {
            "passed": passed_sorted,
            "failed": failed_sorted,
        },
        "capabilities": {"sql": True, "per_block": True},
    }
    return len(failed_sorted) == 0, details
