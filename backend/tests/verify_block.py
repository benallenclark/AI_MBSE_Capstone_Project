from neo4j import GraphDatabase

# --- CONFIGURATION ---
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_AUTH = ("neo4j", "password")
TARGET_ID = "_17_0_4_2_5b40207_1385442147025_135849_11271"  # Star Scanner ID


def investigate_element():
    """Investigate a specific element in the Neo4j database to verify its relationships."""
    print(f"Investigating: Looking up ID {TARGET_ID}...")

    with GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH) as driver:
        with driver.session() as session:
            # 1. Verify the Node Exists
            node = session.run(
                "MATCH (n:Element {id: $id}) RETURN n", id=TARGET_ID
            ).single()
            if not node:
                print("ERROR: Node not found in database!")
                return

            node_data = node["n"]
            print(f"\nFound Node: {node_data.get('name')} ({node_data.get('type')})")
            print(f"   Documentation: {node_data.get('doc', 'None')[:50]}...")

            # 2. Dump ALL outgoing relationships (The "Proof")
            print("\nOutgoing Relationships (What does this connect to?):")
            results = session.run(
                """
                MATCH (n:Element {id: $id})-[r]->(target)
                RETURN type(r) as rel_type, target.name as target_name, target.type as target_type
            """,
                id=TARGET_ID,
            )

            count = 0
            has_requirement = False
            for record in results:
                count += 1
                r_type = record["rel_type"]
                t_name = record["target_name"]
                t_type = record["target_type"]

                print(f"   - [{r_type}] --> {t_name} ({t_type})")

                if r_type == "SATISFY":
                    has_requirement = True

            if count == 0:
                print("   (No outgoing relationships found)")

            # 3. The Verdict
            print("\nVERDICT:")
            if has_requirement:
                print(
                    "   FAIL: Evidence contradicts report. Block DOES satisfy a requirement."
                )
            else:
                print("   PASS: Confirmed. Block has NO 'SATISFY' relationships.")


if __name__ == "__main__":
    investigate_element()
