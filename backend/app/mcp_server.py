import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase

# --- CONFIGURATION ---
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_AUTH = ("neo4j", "password")
REPORTS_DIR = os.path.join(os.getcwd(), "reports")

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)

mcp = FastMCP("Cameo Maturity Agent")

# --- PREDICATES (Single Source of Truth) ---
PREDICATES = [
    (
        "MAT-001",
        "Viewpoints must have a Stakeholder",
        """
        MATCH (v:Element) WHERE v.type = 'Viewpoint' OR v.stereotypes CONTAINS 'Viewpoint'
        OPTIONAL MATCH (v)-[r]-(s:Element) 
        WHERE s.type = 'Stakeholder' OR s.stereotypes CONTAINS 'Stakeholder'
        WITH v, count(s) as stakeholder_count
        WHERE stakeholder_count = 0
        RETURN v.id as id, v.name as name, 'Missing Stakeholder' as issue
        """,
    ),
    (
        "MAT-002",
        "Blocks must satisfy at least one Requirement",
        """
        MATCH (b:Element {type: 'Block'})
        OPTIONAL MATCH (b)-[:SATISFY]->(r:Element {type: 'Requirement'})
        WITH b, count(r) as req_count
        WHERE req_count = 0
        RETURN b.id as id, b.name as name, 'Block has no Requirements' as issue
        """,
    ),
]


def get_db_driver():
    """ "Helper to get Neo4j driver."""
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


# --- TOOL 1: THE EXECUTIVE SUMMARY ---
@mcp.tool()
def check_maturity_status() -> str:
    """
    Runs a quick diagnostic of the model maturity.
    Returns only PASS/FAIL status and violation counts.
    Does NOT return specific element names.
    Use this to decide if a full report is needed.
    """
    summary_lines = ["# Maturity Diagnostic\n"]

    with get_db_driver() as driver, driver.session() as session:
        for rule_id, description, query in PREDICATES:
            # Count violations only (Fast)
            count_query = f"CALL {{ {query} }} RETURN count(*) as c"
            count = session.run(count_query).single()["c"]

            status = "PASS" if count == 0 else f"FAIL ({count} violations)"
            summary_lines.append(f"- **{rule_id}**: {status}")
            summary_lines.append(f"  *Rule: {description}*")

    return "\n".join(summary_lines)


# --- TOOL 2: THE ARTIFACT GENERATOR ---
@mcp.tool()
def generate_evidence_document(format: str = "markdown") -> str:
    """
    Generates a detailed evidence file containing ALL violations.
    Use this when the user asks for the full report or "details".
    Returns the file path of the generated document.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"maturity_report_{timestamp}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Full Maturity Evidence Report\n")
        f.write(f"**Generated:** {datetime.now()}\n\n")

        with get_db_driver() as driver, driver.session() as session:
            for rule_id, description, query in PREDICATES:
                f.write(f"## {rule_id}: {description}\n")

                result = session.run(query)
                violations = [r.data() for r in result]

                if not violations:
                    f.write("### Status: PASS\n\n")
                else:
                    f.write(f"### Status: FAIL ({len(violations)} items)\n")
                    f.write("| Type | Name | ID | Issue |\n")
                    f.write("|---|---|---|---|\n")
                    for v in violations:
                        # Sanitize table columns
                        name = v.get("name", "Unnamed").replace("|", "-")
                        vid = v.get("id", "Unknown")
                        issue = v.get("issue", "Violation")
                        f.write(f"| Element | {name} | `{vid}` | {issue} |\n")
                    f.write("\n")

    return f"Report generated successfully: {filepath}"


if __name__ == "__main__":
    mcp.run()
