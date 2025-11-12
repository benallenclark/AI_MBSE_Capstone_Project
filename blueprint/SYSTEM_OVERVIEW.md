# SYSTEM OVERVIEW

## 1. Purpose

This document guides development for the MBSE Maturity Evaluation Platform.  
It explains how the system fits together, where each part lives, and how to operate or extend it.

---

## 2. Diagrams

- [View System Overview (Simplified) ›](../blueprint/diagrams/simplified_system_overview.png)
- [View System Overview (Detailed) ›](../blueprint/diagrams/detailed_system_overview.png)
- [View System Architecture Diagram ›](../blueprint/diagrams/system_architecture.png)
- [View Request-to-Result Flow Diagram ›](../blueprint/diagrams/request_result_flow.png)

---

## 3. Folder Map

| Area                | Path                            | Purpose                                                           |
| ------------------- | ------------------------------- | ----------------------------------------------------------------- |
| **System Overview** | `/blueprint/SYSTEM_OVERVIEW.md` | You are here                                                      |
| **Frontend**        | `/frontend`                     | React + Vite UI                                                   |
| **Blueprint**       | `/blueprint`                    | Diagrams + architecture docs                                      |
| **Backend/**        | `backend/app/artifacts`         | Packaged assets (e.g., RAG schema, static resources)              |
|                     | `backend/app/ingest`            | XML → DuckDB pipeline; IR views and normalization                 |
|                     | `backend/app/infra`             | Infrastructure: config, paths, jobs DB, maintenance utilities     |
|                     | `backend/app/interface`         | API (v1) + bridge use-cases wiring API to domain/infra            |
|                     | `backend/app/knowledge`         | Domain logic (criteria/predicates, runner, protocols)             |
|                     | `backend/app/rag`               | Retrieval (FTS), prompt building, LLM clients/calls               |
|                     | `backend/ops/data`              | Ephemeral per-model runtime (duckdb, evidence, summaries, RAG DB) |
|                     | `backend/ops/persistent`        | Post-run snapshots for audit (`evidence.jsonl`, summaries)        |
|                     | `backend/samples/`              | Models that are being tested                                      |

---

## 4. Request to Result

**1. Upload →** `POST /v1/analyze/upload`

- Ingest parses XML → builds `model.duckdb`
- Creates IR views + writes `evidence/evidence.jsonl`

**2. Run Criteria →** `app/knowledge/criteria/runner.py`

- Executes predicates (MML-1…N)
- Emits `summary.json` and `summary.api.json` (UI-ready)

**3. Build RAG (between 2 and 3) →** `app/rag/*`

- Packs per-model retrieval DB: `rag.sqlite` (FTS5 + docs)
- Preps prompt builders for explanations and follow-ups

**4. Snapshot →** `app/infra/utils/maintenance.py`

- Copies `evidence.jsonl`, `summary.json`, `summary.api.json` → `backend/ops/persistent/<model_id>/`

**5. Frontend fetch →** `GET /v1/models/{model_id}`

- API serves only the prebuilt `summary.api.json`
- If missing, returns **404**

**6. (Optional) Prompt LLM →**

- Non-stream: `POST /v1/rag/ask`
- Stream: `POST /v1/rag/ask_stream` (SSE/NDJSON)
- Uses `rag.sqlite` + prompt builders to generate cited, evidence-aware answers

---

## 5. Runbook

### Backend (Python 3.12.10 + FastAPI)

**Prerequisite - Install Python 3.12.10**

- Go to official download page:
  - https://www.python.org/downloads/release/python-31210/
  - Scroll down to the "Files" section
  - Under Windows, choose:
    - Windows installer (64-bit) -> python-3.12.10-amd64.exe
  - Run the installer
    - Check "Add Python to PATH" before clicking _Install Now_
  - Verify Installation
    - py -3.12 --version
    - _You should see Python 3.12.10_

**1. Create and activate a virtual environment**

```bash
    cd backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate
    python -V # should show 3.12.10
```

**2. Upgrade pip**

```bash
    python -m pip install -U pip
```

**3. Install backend in editable mode**

```bash
    pip install -e .[dev,docs,rag]
```

**4. Run the API server**

```bash
    uvicorn app.main:app --reload
    # The API docs will be at http://127.0.0.1:8000/v1/docs
```

**5. Analyze a model and inspect output**

- You can test the backend by running the **frontend**, which calls the API endpoints.

### Local LLM Setup (Ollama Installation & Verification)

_Enable the Retrieval-Augmented Generation (RAG) layer to use a local large language model (LLM) via Ollama_

**1. Download and Install Ollama**

- Visit the official download page:
  - https://ollama.com/download
  - Choose your platform (Windows, macOS, or Linux) and install normally.
  - After installation, open a new terminal or PowerShell window.

**2. Verify Ollama Installation**

```bash
    ollama --version
```

_Expected output:_

You should see something like: ollama version is 0.12.10

**3. Check Available Models**

```bash
    ollama list
```

If no models appear, you’ll need to download one (see next step).

**4. Download the Required Model**

By default, the backend expects a small, local model for reasoning (you can adjust in `app/core/config.py`):

```bash
    ollama pull llama3.2:1b
```

You can substitute `llama3.2:1b` for other models (e.g., phi3:mini, mistral, etc.) depending on your machine’s resources.

**5. Verify Model Runs Correctly**

Run a quick chat test:

```bash
    ollama run llama3.2:1b
```

Then type something simple like:

```bash
    > Hello!
```

If the model responds, your LLM is correctly installed and working.

### Frontend (React + TypeScript)

**1. Navigate to the frontend directory**

```bash
    cd frontend
```

**2. Install dependencies**

```bash
    npm install
```

**3. Start development server**

```bash
    npm run dev
```

**4. Run Storybook (for isolated component testing)**

```bash
    npm run storybook
```

## 6. Design Principles

- Single Source of Truth - One backend, one database, one JSON evidence chain shared across API, UI, and RAG.
- Deterministic Core - All maturity logic runs via transparent predicates; every result is reproducible.
- Evidence-First - Every conclusion traces back to specific data and model elements.
- Ephemeral by Default - Uses per-run SQLite and DuckDB; no raw XML persisted unless explicitly configured.
- Explainable AI - The LLM narrates findings, never decides outcomes.
- Composable Layers - Each stage (ingest → criteria → evidence → RAG) is isolated yet interoperable.
- Human-Readable Internals - Code, data, and logs are designed to be inspectable and self-documenting.
