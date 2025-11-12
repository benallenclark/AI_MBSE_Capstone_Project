```text
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── analyze.py        # /v1/analyze (JSON) + /upload (multipart); runs pipeline/job
│   │   │   ├── health.py         # /v1/health (and /ready if desired)
│   │   │   ├── jobs.py           # /v1/jobs/{id}; status/progress/timings/links
│   │   │   ├── models.py         # Pydantic contracts (Vendor, AnalyzeRequest, responses)
│   │   │   ├── models_read.py    # GET /v1/models/{id}; call service; return contract
│   │   │   ├── rag_stream.py     # /v1/rag/ask_stream → SSE/NDJSON streaming via service.ask_stream
│   │   │   ├── rag.py            # /v1/rag/ask; retrieve → pack → LLM
│   │   │   └── serializer/
│   │   │       ├── jobs.py         # Map JobRow → public job payload; add links
│   │   │       └── analysis.py     # Map Evidence → PredicateResult; fingerprint
│   │   │
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
│   │   ├── errors.py           # Ingest exception types (I/O, DuckDB, file writes)
│   │   ├── jsonl_writer.py     # Write per-table JSONL with LRU handle limiting
│   │   ├── loader_duckdb.py    # XML → Parquet → DuckDB; compute model_id
│   │   ├── normalize_rows.py   # Stream rows; fill missing columns using defaults.
│   │   ├── duckdb_utils.py     # COPY JSONL→Parquet; create views; count rows
│   │   ├── schema_config .py   # XML tag/attr config with namespace-safe matching.
│   │   ├── duckdb_connection.py          # Open DuckDB connection with PRAGMAs applied
│   │   └── types.py            # TypedDicts for ingest results and table counts
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
│   │   ├── prompts.py          # Construct prompts and short summaries from cards
│   │   ├── retrieve.py         # FTS retrieval + filters
│   │   ├── schema.sql          # DDL for rag.sqlite
│   │   ├── service.py          # retrieve → pack → LLM → answer
│   │   ├── types.py            # Type definitions for RAG cards, answers, citations
│   │   └── client.py/
│   │       ├── ollama_client.py   # Ollama HTTP client: options, streaming, fallback
│   │       └── protocols.py/      # LLM client Protocol: generate() and stream()
│   │
│   │
│   ├── services/
│   │   ├── analysis.py         # Orchestrate: sync analyze, post-ingest, background job
│   │   ├── jobs.py             # Persist model.xml; fetch/synthesize job rows
│   │   └── models_read.py      # Read model: open DuckDB, build Context, run preds
│   │
│   │
│   ├── utils/
│   │   ├── hashing.py          # compute_sha256 (bytes/stream); pure helpers
│   │   ├── logging_extras.py   # LoggerAdapter helpers: bind cid and context
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
