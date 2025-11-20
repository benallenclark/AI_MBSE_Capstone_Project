# ingest_and_verify.py

from neo4j import GraphDatabase

from app.core.config import NEO4J_AUTH, NEO4J_URI
from app.services import ingestion

JSONL_FILE = "maturity.jsonl"


def run_smoke_test():
    """Ingest a JSONL file via the ingestion service and verify counts in Neo4j."""
    # 1. Setup
    print(" & Init...")
    session_id = ingestion.initialize_session()

    # 2. Ingest via Service
    print("Ingesting...")
    total_nodes = 0
    total_edges = 0

    # Simulate batching like the API would
    current_batch = []
    with open(JSONL_FILE, encoding="utf-8") as f:
        for line in f:
            current_batch.append(line)
            if len(current_batch) >= 1000:
                n, e = ingestion.process_batch(session_id, current_batch)
                total_nodes += n
                total_edges += e
                current_batch = []

        if current_batch:
            n, e = ingestion.process_batch(session_id, current_batch)
            total_nodes += n
            total_edges += e

    # 3. Verify (Keep verification logic local to test script)
    verify_counts(total_nodes, total_edges)


def verify_counts(expected_nodes, expected_edges):
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    with driver.session() as session:
        db_nodes = session.run("MATCH (n:Element) RETURN count(n) as c").single()["c"]
        # Note: Match ANY type of relationship
        db_edges = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]

    print(f"File: {expected_nodes} Nodes, {expected_edges} Edges")
    print(f"DB:   {db_nodes} Nodes, {db_edges} Edges")

    if expected_nodes == db_nodes and expected_edges == db_edges:
        print("PASS")
    else:
        print("FAIL")


if __name__ == "__main__":
    run_smoke_test()
