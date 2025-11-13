# tests/rag/test_build_index_views.py
import os
import sqlite3
import tempfile


def test_schema_creates_views():
    from app.infra.core import paths

    sql = paths.schema_sql_text()
    fd, db = tempfile.mkstemp()
    os.close(fd)
    con = sqlite3.connect(db)
    con.executescript(sql)
    # minimally populate doc/fts so views are queryable
    con.execute(
        "INSERT INTO doc(doc_id,title,body_text,doc_type) VALUES('x','t','b','summary')"
    )
    con.commit()
    # v_summaries exists and returns rows
    rows = con.execute("SELECT doc_id,title,body,score FROM v_summaries").fetchall()
    assert rows and rows[0][0] == "x"
    con.close()
