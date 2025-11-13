# ------------------------------------------------------------
# Module: tests/interface/v1/test_get_model_contract.py
# Purpose: Ensure /v1/models/{model_id} matches the frontend's contract.
# ------------------------------------------------------------
from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.infra.core import paths as paths_module
from app.main import app


def _make_fake_model_dir(tmp_path, model_id: str, summary: dict):
    root = tmp_path / "models" / model_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return root


def _assert_backend_model_response_schema(
    payload: dict[str, Any], model_id: str
) -> None:
    """Assert payload matches BackendModelResponse interface."""
    assert isinstance(payload, dict)
    assert payload["model_id"] == model_id
    assert isinstance(payload["schema_version"], str)
    assert isinstance(payload["model"], dict)
    assert isinstance(payload["model"]["vendor"], str)
    assert isinstance(payload["model"]["version"], str)
    assert isinstance(payload["maturity_level"], int)

    counts = payload["counts"]
    for k in (
        "predicates_total",
        "predicates_passed",
        "predicates_failed",
        "evidence_docs",
    ):
        assert k in counts and isinstance(counts[k], int)

    assert isinstance(payload["fingerprint"], str)

    levels = payload["levels"]
    assert isinstance(levels, dict)
    for _, level_data in levels.items():
        np = level_data["num_predicates"]
        for k in ("expected", "present", "passed", "failed", "missing"):
            assert isinstance(np[k], int)
        for pred in level_data["predicates"]:
            assert isinstance(pred["id"], str)
            assert isinstance(pred["passed"], bool)
            assert isinstance(pred["counts"], dict)


def test_read_model_contract_matches_frontend_interface(tmp_path, monkeypatch):
    """GET /v1/models/{model_id} should match BackendModelResponse contract."""
    model_id = "test-model-123"

    fake_summary = {
        "schema_version": "1.0",
        "model_id": model_id,
        "model": {"vendor": "sparx", "version": "17.1"},
        "maturity_level": 2,
        "counts": {
            "predicates_total": 3,
            "predicates_passed": 1,
            "predicates_failed": 2,
            "evidence_docs": 10,
        },
        "fingerprint": "abc123finger",
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

    fake_dir = _make_fake_model_dir(tmp_path, model_id, fake_summary)

    monkeypatch.setattr(paths_module, "model_dir", lambda mid: fake_dir)
    monkeypatch.setattr(
        "app.interface.api.v1.get_model.get_latest_job",
        lambda mid: {"id": 1, "status": "done"},
    )
    monkeypatch.setattr(
        "app.knowledge.criteria.summary_service.get_summary_for_api",
        lambda mid: fake_summary,
    )

    client = TestClient(app)
    resp = client.get(f"/v1/models/{model_id}")
    assert resp.status_code == 200
    payload = resp.json()
    _assert_backend_model_response_schema(payload, model_id)
