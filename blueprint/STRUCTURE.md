```text
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── analyze.py        # /v1/analyze (JSON) + /upload (multipart); runs pipeline/job
│   │   │   ├── health.py         # /v1/health (and /ready if desired)
│   │   │   ├── jobs.py           # /v1/jobs/{id}; status/progress/timings/links
│   │   │   ├── models.py         # Pydantic contracts (Vendor, AnalyzeRequest, responses)
│   │   │   ├── schemas.py        # /v1/models/* (summary, artifacts, evidence)
│   │   │   ├── rag_stream.py     # /v1/rag/ask_stream → SSE/NDJSON streaming via service.ask_stream
│   │   │   └── rag.py            # /v1/rag/ask; retrieve → pack → LLM
│   │   └── routes.py             # Compose and register v1 routers
│   │
│   ├── core/
│   │   ├── config.py             # Pydantic settings (env-driven)
│   │   ├── jobs_db.py            # Minimal jobs SQLite (idempotency/progress)
│   │   ├── lifespan.py           # Startup/shutdown hooks
│   │   ├── logging_config.py     # Unified logging setup
│   │   ├── orchestrator.py       # Ingest → IR → predicates → RAG (single runner)
│   │   └── paths.py              # Single source of truth for repo/data paths
│   │
│   ├── criteria/
│   │   ├── __init__.py
│   │   ├── loader.py             # Discover predicate modules
│   │   ├── protocols.py          # Predicate interfaces + Context
│   │   ├── runner.py             # Execute predicates; emit Evidence v2 rows
│   │   ├── utils.py              # Execute predicates; emit Evidence v2 rows
│   │   ├── mml_1/
│   │   │   ├── __init__.py
│   │   │   └── predicate_count_tables.py   # Core tables present & populated
│   │   ├── mml_2/
│   │   │   ├── __init__.py
│   │   │   ├── predicate_nonempty_names.py
│   │   │   └── predicate_block_has_ports.py# Blocks have ≥1 typed port
│   │   ├── mml_3/
│   │   │   └── __init__.py                 # Placeholder
│   │   └── mml_4/
│   │       └── __init__.py                 # Placeholder
│   │
│   ├── evidence/
│   │   ├── api.py              # Thin façade: emit Evidence v2 and list/read artifacts
│   │   ├── builder.py          # Build Evidence v2 cards (summary + entities)
│   │   ├── types.py            # EvidenceCard / PredicateOutput types
│   │   └── writer.py           # Write evidence.jsonl; optional Parquet mirror
│   │
│   ├── ingest/
│   │   ├── build_ir.py         # Create IR views/tables in DuckDB
│   │   ├── discover_schema.py  # Normalize XML tables/columns
│   │   └── loader_duckdb.py    # XML → Parquet → DuckDB; compute model_id
│   │
│   ├── input_adapters/
│   │   ├── cameo/
│   │   │   └── .gitkeep
│   │   ├── sparx/
│   │   │   └── v17_1/
│   │   │       └── adapter.py  # Sparx v17.1 normalization rules
│   │   ├── protocols.py        # Adapter contract
│   │   └── router.py           # Choose adapter by vendor/version
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── bootstrap_index.py  # Build per-model rag.sqlite from evidence.jsonl
│   │   ├── db.py               # Open/query rag.sqlite (FTS5)
│   │   ├── llm.py              # Ollama/OpenAI provider wrappers
│   │   ├── pack.py             # Build prompt from retrieved docs
│   │   ├── retrieve.py         # FTS retrieval + filters
│   │   ├── schema.sql          # DDL for rag.sqlite
│   │   └── service.py          # retrieve → pack → LLM → answer
│   │
│   ├── utils/
│   │   └── timing.py           # Monotonic timers & helpers
│   │
│   ├── main.py                 # FastAPI app factory/entrypoint
│   └── __init__.py
│
├── data/
│   ├── models/
│   │   └── <model_id>/
│   │       ├── model.xml
│   │       ├── model.duckdb
│   │       ├── evidence/
│   │       │   └── evidence.jsonl
│   │       ├── parquet/
│   │       └── rag.sqlite      # Per-model RAG index (FTS5)
│   └── jobs.sqlite             # Jobs DB (WAL)
│
├── docs/                       # Sphinx/docs
├── samples/
│   ├── sparx/
│   │   └── v17_1/
│   │       ├── APE-ReferenceModel.xml
│   │       └── DellSat-77_System.xml
│   └── cameo/
│
├── tests/
│
├── tools/
│   └── run_pipeline.py         # CLI: end-to-end pipeline (no API)
│
└── pyproject.toml

```
