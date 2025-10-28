-- app/tempdb/schema.sql
-- Purpose:
--   Base schema for the in-memory SQLite temp DB produced by XML parsing.
--   Tables mirror common Sparx-style t_* structures used by SQL predicates.
--   Keep vendor-agnostic; adapters handle source quirks.
--
-- Dev notes:
--   - Keys are TEXT because upstream IDs/guids are strings in XML.
--   - Use UNIQUE on GUIDs when available; many preds join via GUID.
--   - Foreign keys are NOT enforced (parsing may load out of order).
--   - Add indexes only when predicates depend on them; keep inserts fast.

PRAGMA foreign_keys = OFF;
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = MEMORY;

-- =========================
-- Core tables
-- =========================
CREATE TABLE IF NOT EXISTS t_package(
  package_id    TEXT PRIMARY KEY,
  parent_id     TEXT,   -- parent package_id (nullable for roots)
  name          TEXT,
  stereotype    TEXT,
  scope         TEXT,
  version       TEXT,
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_t_package_parent ON t_package(parent_id);
CREATE INDEX IF NOT EXISTS idx_t_package_guid   ON t_package(guid);

CREATE TABLE IF NOT EXISTS t_object(
  object_id     TEXT PRIMARY KEY,
  package_id    TEXT,   -- FK-like reference to t_package.package_id
  name          TEXT,
  type          TEXT,   -- UML meta-type (Block, Requirement, Activity, etc.)
  stereotype    TEXT,
  status        TEXT,
  author        TEXT,
  complexity    TEXT,
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_t_object_pkg   ON t_object(package_id);
CREATE INDEX IF NOT EXISTS idx_t_object_type  ON t_object(type);
CREATE INDEX IF NOT EXISTS idx_t_object_guid  ON t_object(guid);

-- =========================
-- Constraints and properties
-- =========================
CREATE TABLE IF NOT EXISTS t_objectconstraint(
  id            TEXT PRIMARY KEY,
  object_id     TEXT,   -- → t_object.object_id
  name          TEXT,
  type          TEXT,
  status        TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_constr_obj ON t_objectconstraint(object_id);

CREATE TABLE IF NOT EXISTS t_objectproperties(
  id            TEXT PRIMARY KEY,
  object_id     TEXT,   -- → t_object.object_id
  property      TEXT,   -- key
  value         TEXT,   -- value
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_objprops_obj ON t_objectproperties(object_id);
CREATE INDEX IF NOT EXISTS idx_objprops_key ON t_objectproperties(property);

-- =========================
-- Attributes and tags
-- =========================
CREATE TABLE IF NOT EXISTS t_attribute(
  attribute_id  TEXT PRIMARY KEY,
  object_id     TEXT,   -- owning element → t_object.object_id
  name          TEXT,
  type          TEXT,
  stereotype    TEXT,
  lower_bound   TEXT,
  upper_bound   TEXT,
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_attr_obj   ON t_attribute(object_id);
CREATE INDEX IF NOT EXISTS idx_attr_guid  ON t_attribute(guid);

CREATE TABLE IF NOT EXISTS t_attributetag(
  id            TEXT PRIMARY KEY,
  attribute_id  TEXT,   -- → t_attribute.attribute_id
  property      TEXT,
  value         TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_attrtag_attr ON t_attributetag(attribute_id);
CREATE INDEX IF NOT EXISTS idx_attrtag_key  ON t_attributetag(property);

-- =========================
-- Operations and parameters
-- =========================
CREATE TABLE IF NOT EXISTS t_operation(
  operation_id  TEXT PRIMARY KEY,
  object_id     TEXT,   -- owning element → t_object.object_id
  name          TEXT,
  return_type   TEXT,
  stereotype    TEXT,
  scope         TEXT,
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_op_obj   ON t_operation(object_id);
CREATE INDEX IF NOT EXISTS idx_op_guid  ON t_operation(guid);

CREATE TABLE IF NOT EXISTS t_operationparams(
  id            TEXT PRIMARY KEY,
  operation_id  TEXT,   -- → t_operation.operation_id
  name          TEXT,
  type          TEXT,
  default_value TEXT
);
CREATE INDEX IF NOT EXISTS idx_opparams_op ON t_operationparams(operation_id);

-- =========================
-- Connectors and tags
-- =========================
CREATE TABLE IF NOT EXISTS t_connector(
  connector_id  TEXT PRIMARY KEY,
  name          TEXT,
  type          TEXT,   -- e.g., Association, Dependency, Satisfy, Allocate
  stereotype    TEXT,
  src_object_id TEXT,   -- → t_object.object_id
  dst_object_id TEXT,   -- → t_object.object_id
  direction     TEXT,   -- Unspecified, Source -> Destination, etc.
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_conn_src    ON t_connector(src_object_id);
CREATE INDEX IF NOT EXISTS idx_conn_dst    ON t_connector(dst_object_id);
CREATE INDEX IF NOT EXISTS idx_conn_type   ON t_connector(type);
CREATE INDEX IF NOT EXISTS idx_conn_guid   ON t_connector(guid);

CREATE TABLE IF NOT EXISTS t_connectortag(
  id            TEXT PRIMARY KEY,
  connector_id  TEXT,   -- → t_connector.connector_id
  property      TEXT,
  value         TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_conntag_conn ON t_connectortag(connector_id);
CREATE INDEX IF NOT EXISTS idx_conntag_key  ON t_connectortag(property);

-- =========================
-- Diagrams and placements
-- =========================
CREATE TABLE IF NOT EXISTS t_diagram(
  diagram_id    TEXT PRIMARY KEY,
  package_id    TEXT,   -- → t_package.package_id
  parent_id     TEXT,   -- owning diagram (tool-specific)
  name          TEXT,
  type          TEXT,   -- BDD, IBD, Activity, Parametric, Requirement, etc.
  version       TEXT,
  guid          TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_dgm_pkg    ON t_diagram(package_id);
CREATE INDEX IF NOT EXISTS idx_dgm_parent ON t_diagram(parent_id);
CREATE INDEX IF NOT EXISTS idx_dgm_guid   ON t_diagram(guid);

CREATE TABLE IF NOT EXISTS t_diagramobjects(
  id            TEXT PRIMARY KEY,
  diagram_id    TEXT,   -- → t_diagram.diagram_id
  object_id     TEXT,   -- → t_object.object_id
  xpos          TEXT,
  ypos          TEXT,
  width         TEXT,
  height        TEXT
);
CREATE INDEX IF NOT EXISTS idx_dgmobj_dgm ON t_diagramobjects(diagram_id);
CREATE INDEX IF NOT EXISTS idx_dgmobj_obj ON t_diagramobjects(object_id);

CREATE TABLE IF NOT EXISTS t_diagramlinks(
  id            TEXT PRIMARY KEY,
  diagram_id    TEXT,   -- → t_diagram.diagram_id
  connector_id  TEXT,   -- → t_connector.connector_id
  path          TEXT
);
CREATE INDEX IF NOT EXISTS idx_dgmlink_dgm ON t_diagramlinks(diagram_id);
CREATE INDEX IF NOT EXISTS idx_dgmlink_con ON t_diagramlinks(connector_id);

-- =========================
-- Generic tagged values and cross-refs
-- =========================
CREATE TABLE IF NOT EXISTS t_taggedvalue(
  id            TEXT PRIMARY KEY,
  element_guid  TEXT,   -- GUID of any element (object/attr/connector/diagram)
  property      TEXT,
  value         TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_tagv_guid ON t_taggedvalue(element_guid);
CREATE INDEX IF NOT EXISTS idx_tagv_key  ON t_taggedvalue(property);

CREATE TABLE IF NOT EXISTS t_xref(
  xref_id       TEXT PRIMARY KEY,
  name          TEXT,
  type          TEXT,
  client        TEXT,   -- GUID of referencing element
  supplier      TEXT,   -- GUID of referenced element
  description   TEXT
);
CREATE INDEX IF NOT EXISTS idx_xref_client   ON t_xref(client);
CREATE INDEX IF NOT EXISTS idx_xref_supplier ON t_xref(supplier);

-- =========================
-- Lightweight element GUID map (helps joins)
-- =========================
CREATE TABLE IF NOT EXISTS elt_guid_map(
  guid          TEXT PRIMARY KEY,
  object_id     TEXT,   -- nullable; one of object/attribute/connector/diagram
  attribute_id  TEXT,
  connector_id  TEXT,
  diagram_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_elt_guid_object    ON elt_guid_map(object_id);
CREATE INDEX IF NOT EXISTS idx_elt_guid_attribute ON elt_guid_map(attribute_id);
CREATE INDEX IF NOT EXISTS idx_elt_guid_connector ON elt_guid_map(connector_id);
CREATE INDEX IF NOT EXISTS idx_elt_guid_diagram   ON elt_guid_map(diagram_id);
