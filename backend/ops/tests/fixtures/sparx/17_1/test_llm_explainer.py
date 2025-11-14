import json
from pathlib import Path

import requests

API_URL = "http://127.0.0.1:8000/v1/rag/ask"
QUESTION = "Explain the main weaknesses of this model and what to fix first."

"""
Directions:

uvicorn app.main:app --reload
curl http://127.0.0.1:8000/v1/health
ops/data/models/<model_id>/evidence/evidence.jsonl
ops/data/models/<model_id>/rag.sqlite
python ops/tools/eval_llm_explainer.py

should see: Wrote ops/docs/llm_eval/9ad83f38.md

open the files: ops/docs/llm_eval/9ad83f38.md

"""


def eval_model(model_id: str) -> dict:
    """Call the /v1/rag/ask endpoint for a given model_id."""
    payload = {
        "question": QUESTION,
        "scope": {"model_id": model_id},
    }
    resp = requests.post(API_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    # TODO: update this list as you generate more test models
    model_ids = [
        "9ad83f38",  # example model_id
        # "another_model_id_here",
    ]

    out_dir = Path("ops/docs/llm_eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    for mid in model_ids:
        result = eval_model(mid)
        answer = result.get("answer", "")
        citations = result.get("citations", [])
        model_name = result.get("model", "<unknown>")
        provider = result.get("provider", "<unknown>")

        out_path = out_dir / f"{mid}.md"
        out_path.write_text(
            (
                f"# Evaluation for model {mid}\n\n"
                f"- **LLM model:** `{model_name}`\n"
                f"- **Provider:** `{provider}`\n"
                f"- **Question:** {QUESTION}\n\n"
                f"## Answer\n\n"
                f"{answer}\n\n"
                f"## Citations\n\n"
                f"```json\n{json.dumps(citations, indent=2)}\n```"
            ),
            encoding="utf-8",
        )
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
