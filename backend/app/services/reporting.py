import json
import os
from datetime import datetime


def generate_html_report(session_id: str, filter_rule_id: str = None) -> str:
    """
    Generates HTML. If filter_rule_id is provided, only renders that specific rule.
    """
    evidence_path = "evidence.json"

    if not os.path.exists(evidence_path):
        return f"<h1>Report not found for session: {session_id}</h1>"

    with open(evidence_path, encoding="utf-8") as f:
        data = json.load(f)

    # --- FILTERING LOGIC ---
    results = data.get("results", [])
    if filter_rule_id:
        results = [r for r in results if r.get("rule_id") == filter_rule_id]
    # -----------------------

    title_suffix = f" - {filter_rule_id}" if filter_rule_id else " - Full Report"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Maturity Evidence{title_suffix}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
            h1 {{ border-bottom: 2px solid #eee; padding-bottom: 1rem; }}
            .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 2rem; }}
            .nav-link {{ display: inline-block; margin-bottom: 20px; color: #2563eb; text-decoration: none; }}
            
            .rule-block {{ margin-bottom: 2rem; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
            .rule-header {{ padding: 1rem; display: flex; justify-content: space-between; align-items: center; }}
            
            /* Status Colors */
            .PASS {{ background-color: #dcfce7; border-bottom: 1px solid #bbf7d0; }}
            .FAIL {{ background-color: #fee2e2; border-bottom: 1px solid #fecaca; }}
            
            .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }}
            .badge-PASS {{ background: #22c55e; color: white; }}
            .badge-FAIL {{ background: #ef4444; color: white; }}

            /* Table Styles */
            .table-container {{ padding: 1rem; overflow-x: auto; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
            th {{ text-align: left; background: #f9fafb; padding: 8px; border-bottom: 2px solid #eee; }}
            td {{ padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
            tr:hover {{ background-color: #f8f9fa; }}

            /* --- CAMEO LINK STYLING --- */
            .cameo-link {{
                color: #2563eb;
                text-decoration: none;
                font-family: monospace;
                background: #eff6ff;
                padding: 2px 6px;
                border-radius: 4px;
                cursor: pointer;
                border: 1px solid transparent;
                transition: all 0.2s;
            }}
            .cameo-link:hover {{
                background: #dbeafe;
                border-color: #bfdbfe;
                text-decoration: underline;
            }}
            .cameo-link:active {{
                background: #bfdbfe;
            }}
        </style>
        <script>
            /**
             * Pings the local Java plugin to select the element.
             * The plugin is running on localhost:18080/select
             */
            async function selectElement(id) {{
                const url = `http://localhost:18080/select?id=${{id}}`;
                console.log("Navigating to:", url);
                
                try {{
                    // We use 'mode: cors' because the report is likely on a different port than 18080
                    const response = await fetch(url, {{ method: 'GET', mode: 'cors' }});
                    
                    if (response.ok) {{
                        console.log("Cameo selection successful");
                        // Optional: Visual feedback (toast, or flash the row)
                    }} else {{
                        console.error("Cameo returned error:", response.status);
                        alert("Cameo plugin is reachable but returned an error.");
                    }}
                }} catch (error) {{
                    console.error("Connection failed:", error);
                    alert("Could not connect to Cameo.\\n\\n1. Is Cameo Systems Modeler open?\\n2. Is your NavigationServer plugin running on port 18080?");
                }}
            }}
        </script>
    </head>
    <body>
    """

    if filter_rule_id:
        html += f'<a href="/api/report/{session_id}" class="nav-link">&larr; View All Evidence</a>'
        html += f"<h1>Evidence Detail: {filter_rule_id}</h1>"
    else:
        html += "<h1>Maturity Evidence Report</h1>"

    html += f"""
        <div class="meta">
            <strong>Session ID:</strong> {session_id} <br/>
            <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    """

    if not results:
        html += "<p>No evidence found for this specific rule selection.</p>"

    for r in results:
        status = r.get("status", "FAIL")
        rule_id = r.get("rule_id", "UNKNOWN")
        description = r.get("description", "")
        violations = r.get("violations", [])

        # Sort violations alphabetically by 'name' (case-insensitive)
        # We use .get("name", "") to handle cases where name might be missing
        violations.sort(key=lambda x: x.get("name", "").lower())

        html += f"""
        <div class="rule-block" id="{rule_id}">
            <div class="rule-header {status}">
                <div>
                    <span style="font-family:monospace; font-weight:bold; margin-right:1rem;">{rule_id}</span>
                    <span>{description}</span>
                </div>
                <span class="badge badge-{status}">{status}</span>
            </div>
        """

        if violations:
            html += """
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 30%">Element Name</th>
                            <th style="width: 40%">ID (Click to Navigate)</th>
                            <th style="width: 30%">Issue Detail</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for v in violations:
                v_name = v.get("name", "-")
                v_id = v.get("id", "-")
                v_issue = v.get("issue", "-")

                # --- HERE IS THE INTERACTIVE LINK ---
                # We render an anchor that calls our JavaScript function on click
                link_html = f'<a class="cameo-link" onclick="selectElement(\'{v_id}\'); return false;" title="Show in Cameo">{v_id}</a>'

                html += (
                    f"<tr><td>{v_name}</td><td>{link_html}</td><td>{v_issue}</td></tr>"
                )

            html += "</tbody></table></div>"
        else:
            html += "<div class='table-container'><p>No violations found. Logic satisfied.</p></div>"

        html += "</div>"

    html += "</body></html>"
    return html
