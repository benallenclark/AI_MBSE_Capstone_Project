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
| **API**             | `backend/app/api`               | FastAPI endpoints                                         |
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

### Backend (Python)

**1. Create and activate a virtual environment**

```bash
    cd backend
    python -m venv .venv

    # Activate (Windows PowerShell)
    .\.venv\Scripts\Activate
```

**2. Install dependencies**

```bash
    pip install -r requirements.txt
```

**3. Start backend server**

```bash
    uvicorn app.api.main:app --reload
```

**3. Analyze a model**

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
