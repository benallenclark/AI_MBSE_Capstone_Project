import json


def find_duplicates(filepath):
    """Find duplicate edges in a JSONL file."""
    print(f"Scanning {filepath} for duplicates...")
    seen_edges = set()
    duplicates = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)

            if record.get("_kind") == "edge":
                # Create a signature of the edge (Source, Target, ID)
                sig = (record["source"], record["target"], record["id"])

                if sig in seen_edges:
                    duplicates.append(sig)
                else:
                    seen_edges.add(sig)

    print(f"Found {len(duplicates)} duplicate edges.")
    if len(duplicates) > 0:
        print("Example:", duplicates[0])


find_duplicates("maturity.jsonl")
