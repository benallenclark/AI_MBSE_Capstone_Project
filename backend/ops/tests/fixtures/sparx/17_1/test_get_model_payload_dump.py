# ------------------------------------------------------------
# Module: tests/interface/v1/test_get_model_payload_dump.py
# Purpose: Print and write /v1/models/{model_id} JSON payload for inspection.
# ------------------------------------------------------------
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_print_backend_model_payload(monkeypatch, tmp_path):
    """Debugging helper: dump and save the /v1/models/{model_id} payload."""
    model_id = "debug-model"

    fake_summary = {
        "schema_version": "1.0",
        "model_id": model_id,
        "model": {"vendor": "sparx", "version": "17.1"},
        "maturity_level": 2,
        "counts": {
            "predicates_total": 3,
            "predicates_passed": 1,
            "predicates_failed": 2,
            "evidence_docs": 12,
        },
        "fingerprint": "fingerprint123",
        "levels": {
            "1": {
                "num_predicates": {
                    "expected": 2,
                    "present": 2,
                    "passed": 1,
                    "failed": 1,
                    "missing": 0,
                },
                "predicates": [
                    {
                        "id": "mml_1:predicate_a",
                        "passed": True,
                        "counts": {"rows": 5},
                        "source_tables": ["table_a"],
                    },
                    {
                        "id": "mml_1:predicate_b",
                        "passed": False,
                        "counts": {"rows": 3},
                    },
                ],
            }
        },
        "summary": {"total": 3, "passed": 1, "failed": 2},
        "results": [],
    }

    # --- Patch dependencies so route runs end-to-end but with fake data ---
    def _fake_model_dir(mid: str):
        d = tmp_path / "models" / mid
        d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(json.dumps(fake_summary), encoding="utf-8")
        return d

    monkeypatch.setattr("app.infra.core.paths.model_dir", _fake_model_dir)
    monkeypatch.setattr(
        "app.interface.api.v1.get_model.get_latest_job",
        lambda mid: {"id": 42, "status": "done"},
    )
    monkeypatch.setattr(
        "app.knowledge.criteria.summary_service.get_summary_for_api",
        lambda mid: fake_summary,
    )

    client = TestClient(app)
    resp = client.get(f"/v1/models/{model_id}")
    assert resp.status_code == 200

    payload = resp.json()
    print("\n=== /v1/models/{model_id} payload ===")
    print(json.dumps(payload, indent=2))
    print("====================================\n")

    # --- Write to small JSON file next to this test file ---
    out_path = Path(__file__).parent / "get_model_payload_output.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[saved] {out_path}")

    assert "levels" in payload
