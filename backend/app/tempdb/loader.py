# ------------------------------------------------------------
# Module: app/tempdb/loader.py
# Purpose: Stream vendor XML into an in-memory SQLite database for analysis.
# ------------------------------------------------------------


"""XML → in-memory SQLite loader for temporary model databases.

Summary:
    Streams vendor-native XML (e.g., Sparx EA export) and materializes
    normalized `t_*` tables into an in-memory SQLite database for
    predicate-based maturity checks.

Details:
    - Uses `xml.etree.ElementTree.iterparse` for low memory footprint.
    - Creates tables lazily and widens schemas on-the-fly as new columns appear.
    - Avoids disk I/O: `file:mbse?mode=memory&cache=shared` with relaxed PRAGMAs.
    - Optionally applies a base schema from `app/tempdb/schema.sql`.

Developer Guidance:
    - Keep this module vendor-agnostic. Vendor-specific quirks belong in adapters.
    - Always close the returned `sqlite3.Connection` in callers (API routes).
    - Add new table names to `TABLES` only after confirming real usage.
"""

from __future__ import annotations

import collections
import io
import logging
import sqlite3
from typing import Iterable
from xml.etree.ElementTree import iterparse
import re, codecs

# -----------------------------------------------------------------------------
# Globals and configuration
# -----------------------------------------------------------------------------
parse_counts = collections.Counter()
log = logging.getLogger("tempdb.loader")

# Whitelisted tables we recognize and store. Extend cautiously.
TABLES = {
    "t_package", "t_object", "t_objectconstraint", "t_objectproperties",
    "t_attribute", "t_attributetag", "t_operation", "t_operationparams",
    "t_connector", "t_connectortag", "t_diagram", "t_diagramobjects",
    "t_diagramlinks", "t_taggedvalue", "t_xref",
}

# SQLite reserved words we avoid as column names
RESERVED = {"default"}


# -----------------------------------------------------------------------------
# Helpers: XML normalization, attribute casing, and SQLite schema utilities
# -----------------------------------------------------------------------------
# These functions handle low-level tasks such as:
#   - Decoding XML bytes with uncertain or inconsistent encodings
#   - Wrapping XML fragments in a single synthetic root element
#   - Normalizing attribute keys to lowercase
#   - Ensuring SQLite tables and columns exist before insertion
# They isolate messy edge cases so higher-level parsers can assume clean input.
# -----------------------------------------------------------------------------
_XML_ENC_RE = re.compile(br'<\?xml[^>]*encoding=["\']([^"\']+)["\']', re.IGNORECASE)

def _normalize_xml_bytes(xml: bytes) -> bytes:
    """Decode using declared/BOM encoding, then re-encode as UTF-8, stripping XML decl.
    Keeps content intact, then we can safely wrap in a single root."""
    s = xml.lstrip()
    
    # Detect and decode based on BOM or encoding declaration
    if s.startswith(codecs.BOM_UTF8):
        text = s[len(codecs.BOM_UTF8):].decode("utf-8", errors="strict")
    elif s.startswith(codecs.BOM_UTF16_LE) or s.startswith(codecs.BOM_UTF16_BE):
        # let Python detect endian via 'utf-16'
        text = s.decode("utf-16", errors="strict")
    elif s.startswith(codecs.BOM_UTF32_LE) or s.startswith(codecs.BOM_UTF32_BE):
        text = s.decode("utf-32", errors="strict")
    else:
        # Fallback: parse encoding from XML header or assume UTF-8
        m = _XML_ENC_RE.search(s[:200])  # only header
        enc = m.group(1).decode("ascii").strip().lower() if m else "utf-8"
        text = s.decode(enc, errors="strict")
    # Remove the XML declaration to avoid double declarations after wrapping
    text = re.sub(r'^\s*<\?xml[^>]*\?>', '', text, count=1, flags=re.IGNORECASE)
    return text.encode("utf-8")

def _wrap_single_root(xml: bytes) -> bytes:
    """Ensure the XML content has a single root element.
    Useful when vendor exports omit a top-level wrapper."""
    utf8 = _normalize_xml_bytes(xml)
    return b"<root>" + utf8.strip() + b"</root>"

def _attrs_lower(elem) -> dict[str, str]:
    """Return a dict of element attributes with lowercase keys for case-insensitive access."""
    return {k.casefold(): v for k, v in elem.attrib.items()}

def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    """Check whether a table already exists in the SQLite database."""
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone() is not None

def _ensure_table_with_cols(db: sqlite3.Connection, table: str, cols: Iterable[str]) -> None:
    """Create the table if missing, or ensure all expected columns exist.

    Notes:
        - Adds missing columns dynamically.
        - If no columns are provided on first creation, inserts a placeholder.
    """
    cols = list(cols)
    if _table_exists(db, table):
        _ensure_columns(db, table, cols)
    else:
        if not cols: # SQLite disallows empty CREATE TABLE statements
            cols = ["_placeholder"]
        cols_sql = ",".join(f'"{c}" TEXT' for c in cols)
        db.execute(f'CREATE TABLE "{table}" ({cols_sql})')

def _lname(tag: str) -> str:
    """Return local tag name without namespace and in casefolded form.

    Example:
        '{ns}Row' → 'row'
    """
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    return tag.casefold()


def _norm_col(name: str) -> str:
    """Normalize an XML attribute/field name into a safe SQL column name.

    Rules:
        - trim whitespace
        - casefold
        - spaces and non-alphanumerics → underscore
        - escape reserved words
    """
    n = name.strip().casefold().replace(" ", "_")
    n = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in n)
    if n in RESERVED:
        n = f"{n}_value"
    return n

def _ensure_columns(db: sqlite3.Connection, table: str, cols: Iterable[str]) -> None:
    """Add any missing columns to the table to match the provided iterable."""
    cur = db.execute(f'PRAGMA table_info("{table}")')
    have = {r[1].casefold() for r in cur.fetchall()}
    to_add = [c for c in cols if c.casefold() not in have]
    for cn in to_add:
        db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{cn}" TEXT')


def _row_dict(elem) -> dict[str, str]:
    """Extract a row payload from a <row> element.

    Strategy:
        - Prefer attributes on <row> itself.
        - Otherwise collect child fields: name/value attrs or text content.

    Returns:
        dict[str, str]: Column → value mapping with normalized column names.
    """
    if elem.attrib:
        return {_norm_col(k): v for k, v in elem.attrib.items()}
    rec: dict[str, str] = {}
    for child in list(elem):
        name = child.attrib.get("name") or _lname(child.tag)
        val = child.attrib.get("value")
        if val is None:
            val = (child.text or "").strip()
        if name:
            rec[_norm_col(name)] = val
    return rec


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def load_xml_to_mem(xml_bytes: bytes) -> sqlite3.Connection:
    """Parse vendor-native XML bytes into an in-memory SQLite database.

    Args:
        xml_bytes (bytes): Raw XML document as bytes.

    Returns:
        sqlite3.Connection: Live connection to the populated in-memory database.

    Notes:
        - Uses BEGIN/COMMIT around bulk insertion for speed.
        - Widens table schemas dynamically when new columns are encountered.
        - Clears parsed XML elements to keep memory usage low.
    """
    # In-memory shared-cache DB; no persistence on disk.
    xml_bytes = _wrap_single_root(xml_bytes)
    
    db = sqlite3.connect(":memory:", isolation_level="DEFERRED", check_same_thread=False)
    db.executescript(
        "PRAGMA journal_mode=MEMORY;"
        "PRAGMA synchronous=OFF;"
        "PRAGMA temp_store=MEMORY;"
    )

    # Optional base schema (DDL) packaged with the app.
    try:
        from importlib.resources import files
        ddl = files("app.tempdb").joinpath("schema.sql").read_text(encoding="utf-8")
        if ddl.strip():
            db.executescript(ddl)
    except Exception:
        # Best-effort; absence of schema.sql is not fatal.
        pass

    db.execute("BEGIN")
    current_table: str | None = None
    batch_cols: list[str] = []
    batch_rows: list[tuple[str, ...]] = []
    local_counts: dict[str, int] = {}  # local: table → xml rows seen

    def flush_batch() -> None:
        """Insert the accumulated batch for the current table."""
        nonlocal batch_rows
        if current_table and batch_rows:
            cols_sql = ",".join(f'"{c}"' for c in batch_cols)
            qs = ",".join("?" for _ in batch_cols)
            db.executemany(
                f'INSERT INTO "{current_table}" ({cols_sql}) VALUES ({qs})',
                batch_rows,
            )
            batch_rows = []

    # Stream-parse the XML with start/end events
    for event, elem in iterparse(io.BytesIO(xml_bytes), events=("start", "end")):
        name = _lname(elem.tag)

        if event == "start" and name in ("dataset", "dataset_0", "table"):
            attrs = _attrs_lower(elem)
            t = (attrs.get("name") or attrs.get("table") or "").strip().strip('"').strip("'").casefold()
            # accept whitelisted tables; if you want to be looser, use startswith("t_")
            current_table = t if t in TABLES else None
            if current_table:
                batch_cols = []
                batch_rows = []
                # initialize local count bucket so logs don't show missing keys
                local_counts[current_table] = local_counts.get(current_table, 0)

        elif event == "start" and name in ("data", "rows"):
            batch_cols = []
            batch_rows = []

        elif event == "end" and name == "row" and current_table:
            rec = _row_dict(elem) or {"_empty_row": "1"}

            if not batch_cols:
                batch_cols = list(rec.keys())
                _ensure_table_with_cols(db, current_table, batch_cols)
            else:
                extra = [c for c in rec.keys() if c not in batch_cols]
                if extra:
                    _ensure_columns(db, current_table, extra)
                    if batch_rows:
                        pad = tuple("" for _ in extra)
                        for i in range(len(batch_rows)):
                            batch_rows[i] = tuple(batch_rows[i]) + pad
                    batch_cols.extend(extra)

            batch_rows.append(tuple(rec.get(c, "") for c in batch_cols))
            # increment per-table xml row counter
            local_counts[current_table] = local_counts.get(current_table, 0) + 1
            elem.clear()

        elif event == "end" and name in ("data", "rows"):
            flush_batch()
            elem.clear()

        elif event == "end" and name in ("dataset", "dataset_0", "table"):
            flush_batch()
            current_table = None
            elem.clear()

        else:
            if event == "end":
                elem.clear()

    flush_batch()
    db.execute("COMMIT")

    # Optional sanity logs for table counts (useful while bringing up adapters)
    try:
        tables = [
            r[0] for r in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name LIKE 't_%'"
            ).fetchall()
        ]
        for t in sorted(TABLES):
            if t in tables:
                db_cnt = db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                xml_cnt = local_counts.get(t, 0)
                log.info("count %-18s xml_seen=%d db_rows=%d", t, xml_cnt, db_cnt)
    except Exception:
        # Logging should never break the loader.
        pass

    return db
