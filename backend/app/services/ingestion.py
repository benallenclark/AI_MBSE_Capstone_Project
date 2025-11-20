# app/services/ingestion.py
from neo4j import GraphDatabase

from app.core.config import NEO4J_AUTH, NEO4J_URI

driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


def initialize_session():
    """Wipes DB and sets schema constraints."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Element) REQUIRE n.id IS UNIQUE"
        )
    return "session_1"


def process_batch(session_id: str, lines: list[str]):
    """
    Processes a list of JSON strings.
    Determines if they are Nodes or Edges and flushes them to Neo4j.
    Returns tuple: (nodes_processed, edges_processed)
    """
    import json

    node_batch = []
    edge_batch = []

    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        kind = record.get("_kind")

        if kind == "node":
            node_batch.append(record)
        elif kind == "edge":
            edge_batch.append(record)

    with driver.session() as session:
        if node_batch:
            _flush_nodes(session, node_batch)
        if edge_batch:
            _flush_edges(session, edge_batch)

    return len(node_batch), len(edge_batch)


def finalize_session(session_id: str):
    """Cleans up any session-specific resources if needed."""
    pass


def _flush_nodes(session, batch):
    """Flushes a batch of nodes to the database."""
    query = """
    UNWIND $batch AS row
    MERGE (n:Element {id: row.id})
    SET n += row
    """
    session.run(query, batch=batch)


def _flush_edges(session, batch):
    """Flushes a batch of edges to the database."""
    query = """
    UNWIND $batch AS row
    MERGE (s:Element {id: row.source})
    MERGE (t:Element {id: row.target})
    WITH s, t, row
    CALL apoc.merge.relationship(s, row.type, {id: row.id}, {}, t, {}) YIELD rel
    RETURN count(rel)
    """
    session.run(query, batch=batch)
