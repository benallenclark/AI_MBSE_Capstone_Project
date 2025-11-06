# ------------------------------------------------------------
# Module: app/rag/llm.py
# Purpose: LLM adapters (Ollama now; others can be added later)
# ------------------------------------------------------------

from __future__ import annotations
import subprocess, json, urllib.request
from app.core.config import settings

# Input: prompt text (may contain sensitive data); Output: model's response string.
# Sends prompts either over HTTP(S) or to a local CLI—ensure this aligns with your data handling policy.
# Errors (HTTPError, URLError, OSError) are not caught here; callers should handle failures/timeouts.
def ask_ollama(prompt: str, model: str | None = None) -> str:
    
    # Falls back to a configured default; will fail later if that model isn't available at the endpoint/CLI.
    # Prefer explicit `model` in call sites when reproducibility matters.
    model = model or settings.GEN_MODEL
    
    # If this is a URL → network call; otherwise treated as a local executable path.
    # Invariant: set one or the other, not both; misconfiguration leads to runtime errors.
    endpoint = settings.OLLAMA
    
    # HTTP(S) path: your prompt leaves the host. Use HTTPS in production; avoid HTTP for sensitive prompts.
    # Server must implement Ollama’s `/api/generate` contract; mismatches will 4xx/5xx.
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        
        # Sends JSON {"model", "prompt", "stream": False}; non-streaming responses can be large—plan for memory.
        # Consider adding caller-controlled options (temperature, top_p) if needed for determinism.
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/api/generate",
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        # 300s hard timeout; long generations may still exceed this. Handle HTTPError/URLError at call site.
        # Parses `.get("response","")`; nonstandard servers or error JSON may return an empty string.
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8", "ignore")).get("response", "")
        
    # Local CLI path: no timeout → a stuck model can hang the process; consider adding `timeout=` if reliability matters.
    # Only stdout is returned; stderr may contain errors you’ll miss—log or surface it in failure paths.
    out = subprocess.run([endpoint, "run", model], input=prompt.encode("utf-8"), capture_output=True)
    
    # Silently drops undecodable bytes; useful for robustness but can hide encoding issues.
    # Returns raw CLI text (not JSON); keep call sites consistent with the HTTP branch’s plain string.
    return out.stdout.decode("utf-8", errors="ignore")

