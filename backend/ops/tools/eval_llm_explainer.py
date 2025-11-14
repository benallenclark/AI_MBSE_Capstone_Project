# ------------------------------------------------------------
# File: ops/tools/eval_llm_explainer.py
# Purpose: Score LLM answers against a rubric using your real retrieval + prompts.
# Usage:
# python ops/tools/eval_llm_explainer.py --model-id 9ad83f38 --question "How can I improve my maturity score?"
# Env:
#   OLLAMA_HOST=http://127.0.0.1:11434 (for LLM Client)
# ------------------------------------------------------------
import argparse
import re
from typing import Any

from app.artifacts.intelligence.context.prompts import build_prompt
from app.artifacts.intelligence.context.retrieve import retrieve
from app.artifacts.intelligence.context.service import ask


# --- rubric checks (simple, robust) ---
def check_contains_probe(answer: str, pid: str) -> bool:
    return pid in answer


def check_mentions_numbers(answer: str, cards: list[dict]) -> bool:
    candidates: list[str] = []

    for c in cards:
        meta = c.get("metadata") or {}
        counts = meta.get("counts") or {}

        # Generic ok/total
        measure = meta.get("measure") or {}
        ok, total = measure.get("ok"), measure.get("total")
        if isinstance(ok, int) and isinstance(total, int) and total > 0:
            candidates.append(f"{ok} of {total}")
            # also allow a percentage like "~24%" or "24%"
            pct = int(round(100 * ok / total))
            candidates.append(f"{pct}%")
            candidates.append(f"~{pct}%")

        # Block/port common case
        if {"with_ports", "blocks_total"} <= counts.keys() and counts["blocks_total"]:
            wp, bt = counts["with_ports"], counts["blocks_total"]
            candidates.append(f"{wp} of {bt}")
            pct = int(round(100 * wp / bt))
            candidates.append(f"{pct}%")
            candidates.append(f"~{pct}%")

    # Require at least one numeric snippet to be present in the answer
    return any(str(s) in answer for s in candidates if s)


def check_no_framework_meta(answer: str) -> bool:
    banned = [
        "structured hint",
        "maturity level representation",
        "improve the checks",
        "fix the test framework",
        "modify the predicate",
        "change the scoring",
    ]
    return not any(b in answer.lower() for b in banned)


def check_has_actions(answer: str) -> bool:
    # Look for imperative verbs common to modeling actions
    verbs = ["add", "rename", "trace", "link", "connect", "define", "create", "model"]
    return any(re.search(rf"\b{v}\b", answer.lower()) for v in verbs)


def score_answer(answer: str, cards: list[dict]) -> dict[str, Any]:
    checks = {
        "cites_failing_probe": check_contains_probe(answer, "mml_2.block_has_port"),
        "uses_real_numbers": check_mentions_numbers(answer, cards),
        "no_framework_meta": check_no_framework_meta(answer),
        "has_concrete_actions": check_has_actions(answer),
    }
    total = sum(bool(v) for v in checks.values())
    return {"score": total, "out_of": len(checks), "checks": checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()

    scope = {"model_id": args.model_id}

    # Build a prompt preview for debugging (what will the LLM “see”)
    cards = retrieve(args.question, scope=scope, k=args.k)
    prompt = build_prompt(args.question, cards)

    # Call the real pipeline (retrieve → build prompt → LLM) uniformly
    res = ask(question=args.question, scope=scope)
    answer = res["answer"]

    result = score_answer(answer, cards)
    print("---- QUESTION ----")
    print(args.question)
    print("\n---- PROMPT (first 600 chars) ----")
    print(prompt[:600], "...\n")
    print("---- ANSWER ----")
    print(answer, "\n")
    print("---- SCORE ----")
    print(f"{result['score']} / {result['out_of']}")
    for k, v in result["checks"].items():
        print(f"- {k}: {'✅' if v else '❌'}")


if __name__ == "__main__":
    main()
