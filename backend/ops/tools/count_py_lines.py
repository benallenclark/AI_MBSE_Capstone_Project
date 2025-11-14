#!/usr/bin/env python3
"""
Count lines for every .py file NOT ignored by .gitignore, sorted desc.

Usage
  python count_py_lines.py            # full list
  python count_py_lines.py -n 30      # top 30 longest files
  python count_py_lines.py --json     # machine-readable
"""

from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path.cwd()


def _run_git(args: List[str]) -> Tuple[int, str, str]:
    try:
        cp = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return cp.returncode, cp.stdout, cp.stderr
    except FileNotFoundError:
        return 127, "", "git not found"


def files_via_git() -> List[str]:
    """
    Fast path: use git to list tracked + untracked-but-not-ignored files.
    We filter at the source for *.py and exclude .gitignore'd files.
    """
    code, out, err = _run_git(["ls-files", "-co", "--exclude-standard", "*.py"])
    if code == 0:
        return [line.strip() for line in out.splitlines() if line.strip()]
    # Fallback: walk and ask git check-ignore per file (slower but exact).
    py_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # prune common junk; git will also filter via check-ignore below
        dirnames[:] = [
            d
            for d in dirnames
            if d
            not in {
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "node_modules",
                "dist",
                "build",
            }
        ]
        for f in filenames:
            if not f.endswith(".py"):
                continue
            full = Path(dirpath, f)
            rel = os.path.relpath(full, ROOT)
            code, _, _ = _run_git(["check-ignore", "-q", rel])
            if code == 0:
                # ignored
                continue
            py_files.append(rel)
    return py_files


def line_count(path: Path) -> int:
    # Fast + robust for mixed encodings
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except Exception:
        return -1  # mark unreadable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-n", "--top", type=int, default=0, help="show only the top N longest files"
    )
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    files = files_via_git()
    rows = []
    total_lines = 0
    unreadable = 0

    for rel in files:
        p = ROOT / rel
        n = line_count(p)
        if n >= 0:
            rows.append({"file": rel, "lines": n})
            total_lines += n
        else:
            unreadable += 1

    rows.sort(key=lambda r: r["lines"], reverse=True)
    if args.top and args.top > 0:
        rows = rows[: args.top]

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(ROOT),
                    "total_files": len(files),
                    "unreadable": unreadable,
                    "total_lines": total_lines,
                    "files": rows,
                },
                indent=2,
            )
        )
        return

    # Text output
    width = max(5, *(len(str(r["lines"])) for r in rows) or [5])
    print(f"{'LINES':>{width}}  FILE")
    print("-" * (width + 7 + 40))
    for r in rows:
        print(f"{r['lines']:>{width}}  {r['file']}")
    print("-" * (width + 7 + 40))
    print(
        f"Files: {len(files) - unreadable} readable, {unreadable} unreadable | Total lines: {total_lines}"
    )


if __name__ == "__main__":
    sys.exit(main())
