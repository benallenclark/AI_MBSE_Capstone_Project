# ------------------------------------------------------------
# Module: app/criteria/mml_3/predicate_ports_typed.py
# Purpose: Verify all ports are typed (via Classifier or PDATA1 GUID).
# ------------------------------------------------------------
from app.criteria.protocols import Context, DbLike
import logging

log = logging.getLogger("mml_3.ports_typed")

PREDICATE_ID = "ports_typed"

_SQL = """
WITH ports AS (
  SELECT
    p.Object_ID  AS port_id,
    p.ea_guid    AS port_guid,
    p.Name       AS port_name,
    p.Stereotype AS port_stereotype,
    p.ParentID   AS block_oid,
    p.Classifier AS classifier_oid,
    CASE
      WHEN p.PDATA1 IS NULL THEN NULL
      WHEN TRIM(p.PDATA1) IN ('', '<none>', '&lt;none&gt;') THEN NULL
      ELSE UPPER(REPLACE(REPLACE(TRIM(p.PDATA1), '{',''), '}',''))
    END AS pdata1_norm
  FROM t_object p
  WHERE p.Object_Type = 'Port'
)
SELECT
  p.port_id,
  p.port_guid,
  p.port_name,
  p.port_stereotype,
  b.Object_ID   AS block_id,
  b.ea_guid     AS block_guid,
  b.Name        AS block_name,
  COALESCE(cls.Object_ID,  cls_guid.Object_ID,  cls_map.Object_ID)    AS type_id,
  COALESCE(cls.ea_guid,    cls_guid.ea_guid,    cls_map.ea_guid)      AS type_guid,
  COALESCE(cls.Name,       cls_guid.Name,       cls_map.Name)         AS type_name,
  COALESCE(cls.Object_Type,cls_guid.Object_Type,cls_map.Object_Type)  AS type_kind,
  COALESCE(cls.Stereotype, cls_guid.Stereotype, cls_map.Stereotype)   AS type_stereotype,
  CASE
    WHEN cls.Object_ID      IS NOT NULL THEN 'classifier'
    WHEN cls_guid.Object_ID IS NOT NULL THEN 'pdata1_guid_direct'
    WHEN cls_map.Object_ID  IS NOT NULL THEN 'pdata1_guid_map'
    ELSE NULL
  END AS typed_via
FROM ports p
LEFT JOIN t_object b        ON b.Object_ID = p.block_oid
LEFT JOIN t_object cls      ON cls.Object_ID = p.classifier_oid
LEFT JOIN t_object cls_guid
       ON p.pdata1_norm IS NOT NULL
      AND UPPER(REPLACE(REPLACE(cls_guid.ea_guid,'{',''),'}','')) = p.pdata1_norm
LEFT JOIN elt_guid_map gm
       ON p.pdata1_norm IS NOT NULL
      AND UPPER(REPLACE(REPLACE(gm.guid,'{',''),'}','')) = p.pdata1_norm
LEFT JOIN t_object cls_map  ON cls_map.Object_ID = gm.object_id
ORDER BY LOWER(COALESCE(b.Name, '')), LOWER(COALESCE(p.port_name, '')), p.port_id;
"""

def evaluate(db: DbLike, ctx: Context) -> tuple[bool, dict]:
    cur  = db.execute(_SQL)
    cols = [d[0] for d in cur.description]
    raw  = cur.fetchall()

    def rowdict(t): return {cols[i]: t[i] for i in range(len(cols))}

    def rec(r):
        return {
            "block_id":   int(r["block_id"]) if r["block_id"] is not None else None,
            "block_guid": r["block_guid"],
            "block_name": r["block_name"],
            "port_id":    int(r["port_id"]),
            "port_guid":  r["port_guid"],
            "port_name":  r["port_name"],
            "stereotype": r["port_stereotype"],
            "type_id":    int(r["type_id"]) if r["type_id"] is not None else None,
            "type_guid":  r["type_guid"],
            "type_name":  r["type_name"],
            "typed_via":  r["typed_via"],  # 'classifier' | 'pdata1_guid_direct' | 'pdata1_guid_map' | None
        }

    rows = [rowdict(t) for t in raw]
    typed   = [rec(r) for r in rows if r["type_id"] is not None]
    untyped = [rec(r) for r in rows if r["type_id"] is None]

    via_cls   = sum(1 for r in typed if r["typed_via"] == "classifier")
    via_p1d   = sum(1 for r in typed if r["typed_via"] == "pdata1_guid_direct")
    via_p1map = sum(1 for r in typed if r["typed_via"] == "pdata1_guid_map")

    details = {
        "vendor": getattr(ctx, "vendor", ""),
        "version": getattr(ctx, "version", ""),
        "ports_total": len(rows),
        "ports_typed": len(typed),
        "ports_untyped": len(untyped),
        "counts": {"passed": len(typed), "failed": len(untyped)},
        "capabilities": {"sql": True, "per_port": True, "guid_resolve": True},
        "typed_via_counts": {
            "classifier": via_cls,
            "pdata1_guid_direct": via_p1d,
            "pdata1_guid_map": via_p1map,
        },
        "evidence": {"passed": typed, "failed": untyped},
    }

    log.debug(
        "ports_typed vendor=%s version=%s total=%d typed=%d (cls=%d, p1_direct=%d, p1_map=%d) untyped=%d",
        details["vendor"], details["version"],
        details["ports_total"], details["ports_typed"],
        via_cls, via_p1d, via_p1map, details["ports_untyped"],
    )

    return (len(untyped) == 0), details
