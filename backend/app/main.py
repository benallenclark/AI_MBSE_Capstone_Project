from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import OLLAMA_MODEL
from app.services import analysis, chat, ingestion

app = FastAPI()

# Enable CORS so the React frontend (localhost:5173) can talk to Python (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # In production, specify the frontend URL (e.g. ["http://localhost:5173"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state for simplicity (In prod, use Redis)
active_sessions = {}


@app.on_event("startup")
async def startup_event():
    print(f"Backend started. Using LLM: {OLLAMA_MODEL}")


class BatchModel(BaseModel):
    """Model for a batch of lines to ingest."""

    session_id: str
    lines: list[str]  # A list of JSON strings


class FinishModel(BaseModel):
    """Model for finishing an ingestion session."""

    session_id: str


# --- DATA MODELS ---
class ChatMessage(BaseModel):
    """A single message in the chat history."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Model for chat request payload."""

    history: list[ChatMessage]


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Handles chat requests by interacting with the chat agent.
    Expects a history of messages and returns the assistant's response.
    The main chat interface:
    1. Receives chat history from the client.
    2. Passes the history to the chat agent for processing.
    3. Returns the assistant's response to the client.
    """
    try:
        history_dicts = [msg.model_dump() for msg in request.history]
        response_text = chat.chat_with_agent(history_dicts)

        safe = str(response_text or "").strip()
        if not safe:
            safe = "(no content returned by model)"

        return {"role": "assistant", "content": safe}
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/start")
async def start_ingestion():
    """Initializes a new ingestion session and returns a session ID."""
    session_id = ingestion.initialize_session()
    return {"session_id": session_id, "status": "ready"}


@app.post("/api/ingest/batch")
async def receive_batch(batch: BatchModel):
    """Receives a batch of lines to ingest into the database."""
    try:
        count = ingestion.process_batch(batch.session_id, batch.lines)
        return {"processed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/finish")
async def finish_ingestion(payload: FinishModel, background_tasks: BackgroundTasks):
    """Triggers the analysis phase in the background after ingestion is complete."""
    # Extract the ID from the payload object
    session_id = payload.session_id

    # 1. Finalize DB ingestion
    ingestion.finalize_session(session_id)

    # 2. Schedule Analysis in background
    background_tasks.add_task(analysis.run_full_analysis, session_id)

    return {"status": "analysis_started", "message": "Data received. Analysis running."}


@app.get("/api/analysis/{session_id}")
async def get_analysis_results(session_id: str):
    """
    Serve only compact summary JSON. Never return raw evidence.
    - If summary_{session_id}.json exists -> return it.
    - If session_id == 'latest' and summary.json exists -> return it.
    - (Optional) If only evidence exists, try to auto-transform it into a summary
      and return the summary (never the evidence).
    - Otherwise 404 so the frontend keeps polling.
    """
    import json
    import os

    # 1) Per-session summary
    summary_path = "summary.json"
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            return json.load(f)

    # 2) Dev shim: /api/analysis/latest -> summary.json
    if session_id == "latest" and os.path.exists("summary.json"):
        with open("summary.json", encoding="utf-8") as f:
            return json.load(f)

    # 3) Optional: auto-transform evidence -> summary (never return evidence)
    try:
        evidence_path = f"evidence_{session_id}.json"
        if os.path.exists(evidence_path):
            # If you wired a transformer module:
            # from bff_summary import transform
            # with open(evidence_path, "r", encoding="utf-8") as f:
            #     evidence = json.load(f)
            # summary = transform(evidence, vendor="cameo", version="2024x", model_id=session_id)
            # with open(summary_path, "w", encoding="utf-8") as out:
            #     json.dump(summary, out, indent=2)
            # return summary

            # If you prefer to call the script you already have, do this instead:
            # import subprocess, sys
            # subprocess.run([sys.executable, "summarize_evidence.py",
            #                 "--input", evidence_path,
            #                 "--output", summary_path,
            #                 "--vendor", "cameo",
            #                 "--version", "2024x",
            #                 "--model-id", session_id],
            #                check=True)
            # with open(summary_path, "r", encoding="utf-8") as f:
            #     return json.load(f)
            pass
    except Exception:
        # If transform fails, we still never send evidence. Fall through to 404.
        ...

    # 4) Not ready / not found -> keep frontend polling
    raise HTTPException(status_code=404, detail="Summary not found or pending")
