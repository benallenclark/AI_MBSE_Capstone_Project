# ------------------------------------------------------------
# Module: tools/run_pipeline.py
# Purpose: CLI to run ingest → IR → predicates → (optional) RAG for a model.
# ------------------------------------------------------------

from __future__ import annotations

import argparse
from pathlib import Path

from app.flow.orchestrator import compute_model_id, run


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run ingest → IR → predicates → RAG for a model."
    )
    ap.add_argument(
        "--xml",
        type=Path,
        help="Path to model XML. If omitted, reuses existing artifacts.",
        required=False,
    )
    ap.add_argument(
        "--model-id",
        type=str,
        help="Stable id (sha256[:8]). If omitted, derived from --xml.",
        required=False,
    )
    ap.add_argument("--no-rag", action="store_true", help="Skip building rag.sqlite.")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Force re-ingest if artifacts already exist.",
    )
    args = ap.parse_args()

    # Preconditions: require either --xml (to derive id) or --model-id (to reuse artifacts).
    # `ap.error(...)` triggers SystemExit; callers should expect the process to exit here.
    if not args.model_id and not args.xml:
        ap.error("Provide --xml or --model-id (or both).")

    # If --model-id is omitted, `--xml` must be provided and point to a readable file.
    # Passing None to `compute_model_id` will raise—this line relies on the guard above.
    model_id = args.model_id or compute_model_id(args.xml)

    # Runs ingest/IR/predicates and optionally RAG; expect filesystem and DB writes under the model workspace.
    # Long-running; surface errors to the shell so CI can fail fast.
    res = run(
        model_id=model_id,
        xml_path=args.xml,
        overwrite=args.overwrite,
        build_rag=not args.no_rag,
        run_predicates=True,
    )

    print(f"\n=== OK: model_id={res.model_id} ===")
    for k, v in res.artifacts.items():
        print(f"{k:16} {v}")


if __name__ == "__main__":
    main()

    # Module-level `exit(0)` runs on import and will terminate the parent process.
    # Keep exits inside `if __name__ == "__main__":` to avoid killing tools/tests that import this module.
    exit(0)
