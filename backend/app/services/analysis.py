# analysis.py
import json
import traceback

from neo4j import GraphDatabase

from app.core.config import NEO4J_AUTH, NEO4J_URI
from app.services.bff_summary import transform

# --- CONFIGURATION ---
OUTPUT_FILE = "evidence.json"


def mml_for(rule_id: str) -> int:
    """Clamp to 0..10 and default to 0 if unknown."""
    try:
        n = int(RULE_MML.get(rule_id, 0))
    except Exception:
        n = 0
    return max(0, min(MML_MAX_LEVEL, n))


# ---------------------------------------------------

# --- ANALYSIS RULES ---
# Each predicate is a tuple of (rule_id, mml, description, cypher_query)
PREDICATES = [
    # Level 1 — Intent Captured
    (
        "L1.1-REQUIREMENTS-EXIST",
        1,
        "At least one Requirement exists in the model",
        """
        UNWIND [1] AS _
        OPTIONAL MATCH (r:Element {type: 'Requirement'})
        WITH count(r) AS c
        WHERE c = 0
        RETURN '(model)' AS id,
               'Model'    AS name,
               'No Requirement elements found' AS issue
        """,
    ),
    (
        "L2.1-STAKEHOLDER-PRESENT",
        2,
        "Viewpoints must have a Stakeholder",
        """
        MATCH (v:Element) 
        WHERE v.type = 'Viewpoint' OR v.stereotypes CONTAINS 'Viewpoint'
        OPTIONAL MATCH (v)-[r]-(s:Element)
        WHERE s.type = 'Stakeholder' OR s.stereotypes CONTAINS 'Stakeholder'
        WITH v, count(s) as stakeholder_count
        WHERE stakeholder_count = 0
        RETURN v.id as id, v.name as name, 'Missing Stakeholder' as issue
        """,
    ),
    # Level 4 — Foundational Traceability (example)
    (
        "L4.1-BLOCK-SATISFIES-REQUIREMENT",
        4,
        "Blocks must satisfy at least one Requirement",
        """
        MATCH (b:Element {type: 'Block'})
        OPTIONAL MATCH (b)-[:SATISFY]->(r:Element {type: 'Requirement'})
        WITH b, count(r) as req_count
        WHERE req_count = 0
        RETURN b.id as id, b.name as name, 'Block has no Requirements' as issue
        """,
    ),
    # Level 7 — V&V
    (
        "L7.2-REQUIREMENT-VERIFIED-BY-TESTCASE",
        7,
        "Requirements must be verified by a Test Case",
        """
        MATCH (r:Element {type: 'Requirement'})
        OPTIONAL MATCH (tc:Element)-[:VERIFY]->(r)
        WITH r, count(tc) as test_count
        WHERE test_count = 0
        RETURN r.id as id, r.name as name, 'Requirement not verified' as issue
        """,
    ),
]


def run_full_analysis(session_id: str):
    """Runs the full analysis suite and returns the evidence report."""
    print(f"🕵️ [Session {session_id}] Collecting Evidence...", flush=True)

    try:
        evidence_report = {
            "meta": {"generated_at": "Today", "session_id": session_id},
            "results": [],
        }

        with GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH) as driver:
            driver.verify_connectivity()

            with driver.session() as session:
                for rule_id, mml, description, query in PREDICATES:
                    print(f"   Running {rule_id}: {description}...", flush=True)
                    result = session.run(query)
                    violations = [r.data() for r in result]

                    evidence_report["results"].append(
                        {
                            "rule_id": rule_id,
                            "mml": mml,
                            "description": description,
                            "status": "FAIL" if violations else "PASS",
                            "violation_count": len(violations),
                            "violations": violations,
                        }
                    )

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(evidence_report, f, indent=2)

        print(f"Evidence saved to {OUTPUT_FILE}", flush=True)
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            evidence = json.load(f)

        summary = transform(
            evidence, vendor="cameo", version="2024x", model_id=session_id
        )
        with open("summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    except Exception as e:
        print(f"ANALYSIS CRASHED: {e}", flush=True)
        traceback.print_exc()


if __name__ == "__main__":
    run_full_analysis("dev")
