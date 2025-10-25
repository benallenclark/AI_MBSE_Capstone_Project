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

| Area                | Path                            | Purpose                                                   |
| ------------------- | ------------------------------- | --------------------------------------------------------- |
| **API**             | `backend/app/api`               | FastAPI endpoints and routers                             |
| **Core**            | `backend/app/core`              | Config, logging, startup                                  |
| **Criteria**        | `backend/app/criteria/mml_*`    | Maturity ladder logic (criteria per level)                |
| **Input Adapters**  | `backend/app/input_adapters/`   | XML parsers per tool/version (`sparx/v17_1`, `cameo/...`) |
| **RAG**             | `backend/app/rag`               | Retrieval + LLM context builder                           |
| **Tests**           | `backend/tests`                 | Unit and integration tests                                |
| **Contracts**       | `/contracts`                    | Shared schemas between backend and frontend               |
| **Frontend**        | `/frontend`                     | React + Vite UI                                           |
| **Blueprint**       | `/blueprint`                    | Diagrams + architecture docs                              |
| **System Overview** | `/blueprint/SYSTEM_OVERVIEW.md` | You are here                                              |

---

## 4. Runbook

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
    pip install -e .
```

**4. Run the API server**

```bash
    uvicorn app.main:app --reload
    # The API docs will be at http://127.0.0.1:8000/v1/docs
```

**5. Analyze a model**

```bash
    # TODO: show how to do this once analysis endpoint is ready
```

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

## 5. Design Principles

- One backend, one DB, one JSON - shared across API, UI, and LLM/RAG.
- Ephemeral/Temporary storage - SQLite per run, no raw XML unless configured.
- Criteria as code - maturity logic is transparent and traceable.
- Evidence-driven - every conclusion links to source data.
- LLM narrates, never judges.
