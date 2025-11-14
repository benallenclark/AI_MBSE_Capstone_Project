# Project Structure & Mental Model

This backend is designed to be understood as a deterministic, four-stage pipeline.  
It separates cleanly into conceptual layers: **Interface → Flow → Knowledge → Artifacts → Infra**

---

## Goal

> **Make the backend read like a mind map.**  
> Each layer has one job:
>
> - **Interface** exposes the system publicly.
> - **Flow** executes deterministic stages.
> - **Knowledge** defines what “maturity” means.
> - **Artifacts** represent produced data.
> - **Infra** keeps everything running.

## Diagrams

- [View MindMap Idea ›](../blueprint/diagrams/mindmap.png)
- [View Pipeline Overview ›](../blueprint/diagrams/pipeline_overview.png)

**Simply put:**  
`Interface` drives `Flow`;  
`Flow` uses `Knowledge` to create `Artifacts`;  
`Infra` supports it all.

---

## Orientation Map

| Layer         | Description                                                    | Examples                                               |
| ------------- | -------------------------------------------------------------- | ------------------------------------------------------ |
| **Interface** | Public entrypoints — HTTP routes, contracts, service bridges.  | `app/interface/api/*`, `app/interface/bridge/*`        |
| **Flow**      | Deterministic pipeline — ingest → predicates → evidence → RAG. | `app/flow/*`                                           |
| **Knowledge** | Domain logic — what maturity means, how to interpret models.   | `app/knowledge/criteria/*`, `app/knowledge/adapters/*` |
| **Artifacts** | Tangible results and queryable outputs.                        | `app/artifacts/evidence/*`, `app/artifacts/rag/*`      |
| **Infra**     | Core runtime, config, and utilities.                           | `app/infra/core/*`, `app/infra/utils/*`                |

---

## Stable Stage Contracts

Each stage is a callable unit — stable, mockable, and testable in isolation.

| Stage               | Function                                   | Output                                                        |
| ------------------- | ------------------------------------------ | ------------------------------------------------------------- |
| **ingest_stage**    | `run(xml_path, *, model_id=None)`          | `{model_id, duckdb_path, timings, ...}`                       |
| **predicate_stage** | `run(db, ctx, *, groups=None)`             | `(maturity_level, evidence_items, per_level_breakdown)`       |
| **evidence_stage**  | `run(model_dir, *, ctx, predicate_output)` | `[evidence_cards...]`                                         |
| **rag_stage**       | `run(model_id)`                            | `rag.sqlite path`                                             |
| **orchestrator**    | `run_all(...)`                             | `{model_id, maturity_level, levels, duckdb_path, rag_sqlite}` |

---

## Naming Conventions

| Category               | Rule                  | Example                               |
| ---------------------- | --------------------- | ------------------------------------- |
| **Flow**               | Verbs (actions)       | `ingest_stage.py`, `orchestrator.py`  |
| **Knowledge**          | Nouns (concepts)      | `criteria.runner`, `adapters.router`  |
| **Interface / Bridge** | Verbs (API actions)   | `analyze.py`, `get_model.py`          |
| **Artifacts**          | Nouns or data actions | `evidence.writer`, `rag.service`      |
| **Infra**              | Nouns (scaffolding)   | `config.py`, `paths.py`, `jobs_db.py` |

---

## Trace: Request → Answer

1. **API /v1/analyze** → `bridge.analysis` → `flow.orchestrator`
2. **Orchestrator** runs stages: `ingest → predicates → evidence → rag`
3. **API /v1/rag/ask** → `rag.service` uses `rag.sqlite` + LLM → **answer**

---

## Why This Structure Works

- **Navigation by intent.** Every folder describes _why_ it exists, not _what_ it contains.
- **Isolation by design.** Each stage can be tested or swapped independently.
- **Infra is stable; domain evolves freely.**
- **No cross-contamination.** API never touches DuckDB, predicates, or FTS internals.
- **Drill-down clarity:**
  - Interface → Flow → specific stages
  - Knowledge → specific predicates/adapters
  - Artifacts → tangible databases/files

---

## TL;DR

> **Folders are ideas; files are verbs.**
>
> `Interface` talks to `Flow`.  
> `Flow` calls `Knowledge`.  
> `Knowledge` produces `Artifacts`.  
> `Infra` keeps it all together.

---

## Folder Tree Overview

```text
backend/
├── app/
│   ├── interface/                         # Public surface: HTTP + thin bridges
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── health.py              # /v1/health, optional /ready
│   │   │       ├── jobs.py                # /v1/jobs/{id} (poll job status)
│   │   │       ├── models.py              # Pydantic wire contracts (strict)
│   │   │       ├── get_model.py           # GET /v1/models/{id} → read summary.api.json
│   │   │       ├── rag_stream.py          # /v1/rag/ask_stream (SSE/NDJSON)
│   │   │       ├── rag.py                 # /v1/rag/ask (retrieve → pack → LLM)
│   │   │       └── serializers/
│   │   │           ├── jobs.py            # JobRow → JobContract (+links)
│   │   │           └── analysis.py        # EvidenceItem → PredicateResult (+fingerprint)
│   │   ├── bridge/                        # Thin adapters: API → Flow/Infra
│   │   │   ├── analysis.py                # Orchestrate ingest→predicates→evidence→rag
│   │   │   ├── jobs.py                    # Job DB helpers for upload/poll
│   │   │   └── get_model.py               # Read prebuilt summaries for UI
│   │   └── routes.py                      # Mount v1 routers
│   │
│   ├── flow/                              # Deterministic pipeline stages
│   │   ├── ingest_stage.py                # XML→tables→parquet/duckdb
│   │   ├── predicate_stage.py             # Run criteria runner; collect evidence
│   │   ├── evidence_stage.py              # Build/write evidence cards
│   │   ├── rag_stage.py                   # Build RAG index (rag.sqlite)
│   │   └── orchestrator.py                # Run stages, return run summary
│   │
│   ├── knowledge/                         # Domain truth (criteria + adapters)
│   │   ├── criteria/
│   │   │   ├── __init__.py                # Package marker
│   │   │   ├── loader.py                  # Discover predicates by group (mml_N)
│   │   │   ├── protocols.py               # Context/DbLike predicate signatures
│   │   │   ├── build_summary.py           #
│   │   │   ├── summary_service.py         #
│   │   │   ├── runner.py                  # Execute all predicates; emit levels/evidence
│   │   │   ├── utils.py                   # Small helpers for predicate authors
│   │   │   ├── mml_1/
│   │   │   │   ├── __init__.py
│   │   │   │   └── predicate_count_tables.py     # Sanity check: required EA tables
│   │   │   └── mml_2/
│   │   │       ├── __init__.py
│   │   │       ├── predicate_nonempty_names.py   # No empty names on core elements
│   │   │       └── predicate_block_has_port.py   # Blocks expose at least one port
│   │   │
│   │   ├── diagnostics/
│   │   │   └── missing_ports.py            #
│   │   │
│   │   └── adapters/
│   │       ├── protocols.py                # Vendor adapter contracts
│   │       ├── router.py                   # Pick adapter for vendor/version
│   │       ├── cameo/                      # Cameo-specific adapters
│   │       └── sparx/
│   │           └── v17_1/adapter.py        # Sparx 17.1 → IR mapping
│   │
│   ├── artifacts/                         # Data products (evidence + RAG)
│   │   ├── evidence/
│   │   │   ├── api.py                     # Evidence API packers
│   │   │   ├── assembler.py               # Merge predicate outputs → cards
│   │   │   ├── coerce.py                  #
│   │   │   ├── types.py                   # Evidence card types
│   │   │   └── writer.py                  # Write evidence.jsonl (append-only)
│   │   └── rag/
│   │       ├── build_index.py             # Ingest evidence → FTS tables
│   │       ├── db.py                      # SQLite helpers
│   │       ├── llm.py                     # LLM selection/options
│   │       ├── pack.py                    # Prompt/citation packing
│   │       ├── prompts.py                 # Prompt templates
│   │       ├── retrieve.py                # FTS5/BM25 retrieval
│   │       ├── schema.sql                 # RAG DB schema (packaged)
│   │       ├── service.py                 # ask()/ask_stream() orchestration
│   │       ├── types.py                   # RAG-facing types
│   │       └── client/
│   │           ├── ollama_client.py       # Robust Ollama HTTP client
│   │           ├── ollama_http.py         #
│   │           ├── ollama_options.py      #
│   │           └── protocols.py           # LLM client interface
│   │
│   └── infra/                             # Configuration & runtime support
│       ├── core/
│       │   ├── config.py                  # Settings/env (models/paths/llm)
│       │   ├── jobs_db.py                 # jobs.sqlite connect/query helpers
│       │   ├── lifespan.py                # FastAPI lifespan hooks
│       │   ├── logging_config.py          # Structured logging setup
│       │   └── paths.py                   # Canonical paths + snapshot/prune
│       ├── io/
│       │   └── write_summary.py           #
│       └── utils/
│           ├── hashing.py                 # SHA-256 helpers
│           ├── logging_extras.py          # Logger adapters/decorators
│           └── timing.py                  # perf timers + context manager
│
│   ├── main.py                            # FastAPI entrypoint (CORS, routes)
│   └── __init__.py
│
├── ops/                                   # Operations, data, docs, tests
│   ├── tools/
│   │   └── run_pipeline.py                # Local dev: run the full pipeline
│   ├── tests/                             # Unit/integration tests
│   ├── docs/                              # Generated or supporting docs
│   ├── persistent/                        # Placeholder for storing generated evidence per model_id
│   └── data/
│       ├── models/
│       │   └── <model_id>/
│       │       ├── model.xml              # Uploaded source (kept)
│       │       ├── model.duckdb           # Per-run DB (kept for /v1/models)
│       │       ├── summary.json           # Rich run summary (levels + counts)
│       │       ├── summary.api.json       # UI-ready compact results (no fallback)
│       │       ├── evidence/
│       │       │   └── evidence.jsonl     # Append-only predicate evidence
│       │       ├── parquet/               # Ephemeral parquet (pruned post-run)
│       │       └── rag.sqlite             # RAG index (FTS5)
│       └── jobs.sqlite                    # Job state DB
└── pyproject.toml

```
