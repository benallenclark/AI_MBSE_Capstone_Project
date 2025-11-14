# ------------------------------------------------------------
# Test: ops/tests/fixtures/sparx/17_1/test_retrieval_preview.py
# Purpose: Preview exactly which evidence cards retrieval returns; snapshot citations from service.ask()
# ------------------------------------------------------------
# Usage:
# 1) pytest -q ops/tests/fixtures/sparx/17_1/test_retrieval_preview.py -s
# 2) pytest -q ops/tests/fixtures/sparx/17_1/test_retrieval_preview.py::test_dump_all_rankings -s

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Optional: if your code imports OllamaClient.from_settings inside service, we can stub it:
from app.artifacts.intelligence.client.ollama_client import OllamaClient  # type: ignore
from app.artifacts.intelligence.context.retrieve import retrieve
from app.artifacts.intelligence.context.service import ask as service_ask
from app.infra.core import paths
from app.infra.core.config import settings


def _find_model_id() -> str | None:
    """Return a model_id that actually has ops/data/models/<id>/rag.sqlite."""
    # 1) Respect explicit override for CI/local runs
    mid = os.getenv("MBSE_MODEL_ID")
    if mid:
        if (paths.rag_sqlite(mid)).exists():
            return mid

    # 2) Try configured default
    if getattr(settings, "DEFAULT_MODEL_ID", None):
        mid = settings.DEFAULT_MODEL_ID
        if (paths.rag_sqlite(mid)).exists():
            return mid

    # 3) Scan MODELS_DIR for any rag.sqlite
    models_dir: Path = settings.MODELS_DIR
    if models_dir.exists():
        for d in models_dir.iterdir():
            if (d / "rag.sqlite").exists():
                return d.name

    return None


@pytest.fixture(scope="module")
def model_id() -> str:
    mid = _find_model_id()
    if not mid:
        pytest.skip(
            "No rag.sqlite found under ops/data/models. "
            "Run your pipeline to create one, or set MBSE_MODEL_ID to a valid id."
        )
    return mid


def test_retrieve_preview(tmp_path: Path, model_id: str):
    """Call retriever directly and dump the exact cards it returns."""
    question = "How can I improve my maturity score?"
    scope = {"model_id": model_id}
    k = getattr(settings, "RAG_TOP_K", 8)

    cards = retrieve(question, scope, k=k)
    assert isinstance(cards, list), "retriever must return a list"
    assert cards, "retriever returned zero cards (check index/population)"

    out = tmp_path / f"evidence_{model_id}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n--- Top {k} Retrieved Cards (for LLM) ---")
    print(f"Full dump: {out}")
    # Also print to terminal for convenience
    for i, c in enumerate(cards):
        print(f"{i + 1:02d} | score={c.get('score')} | doc_id={c.get('doc_id')}")

    # Sanity: each card should have minimal shape
    for c in cards:
        assert "doc_id" in c or "probe_id" in c
        assert "title" in c or "body" in c


def test_service_citations_snapshot(tmp_path: Path, monkeypatch, model_id: str):
    """Use the same path your LLM uses: ask() → returns 'citations' = the cards it saw (no LLM call)."""

    # --- Stub the LLM client so we don't depend on Ollama being up/pulled ---
    class _DummyClient:
        model = "dummy"

        def generate(self, prompt: str) -> str:
            return "[dummy] ok"

        def stream(self, prompt: str):
            yield "[dummy] ok"

    monkeypatch.setattr(
        OllamaClient, "from_settings", lambda *_args, **_kw: _DummyClient()
    )
    question = "How can I improve my maturity score?"

    scope = {"model_id": model_id}
    res = service_ask(question, scope)

    # We only care about what retrieval fed to the LLM:
    citations = res.get("citations", [])
    assert isinstance(citations, list)
    assert citations, "service returned no citations (retrieval likely empty)"

    out = tmp_path / f"citations_{model_id}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in citations:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("\n--- Citations from service.ask() ---")
    print(f"Full dump: {out} ({len(citations)} citations)")
    # Also print to terminal for convenience
    for i, c in enumerate(citations):
        print(f"{i + 1:02d} | score={c.get('score')} | doc_id={c.get('doc_id')}")


# --- NEW TEST ---
def test_dump_all_rankings(model_id: str):
    """
    Retrieves a large number of cards and prints a ranked list to the console
    to let us see the FULL ranking and find "lost" summary cards.
    """
    question = "How can I improve my maturity score?"
    scope = {"model_id": model_id}
    k = 100  # Retrieve a large number to see the full list

    cards = retrieve(question, scope, k=k)
    assert cards, "retriever returned zero cards"

    print(f"\n--- Full BM25 Ranking Dump (k={k}) for query: '{question}' ---")
    for i, card in enumerate(cards):
        print(f"{i + 1:03d} | score={card.get('score')} | doc_id={card.get('doc_id')}")
        if card.get("doc_type") == "summary":
            print("      ^--- THIS IS A SUMMARY CARD")
