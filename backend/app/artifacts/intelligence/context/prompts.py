# ------------------------------------------------------------
# Module: app/artifacts/intelligence/context/prompts.py
# Purpose: Build RAG-first, representation-first prompts for model maturity answers.
# ------------------------------------------------------------

"""Prompt builders for *representation maturity*, synthesized strictly from retrieved evidence.

Principles
----------
- Representation-first: maturity judges the *model-as-representation*, not whether the design is a good solution.
- RAG-first: the LLM only reasons over the provided evidence subset; if evidence is missing, say so.
- Numeric guardrails: quote counts only when present in evidence; never invent or "carry over" numbers.

API
---
- pack_context(cards)  -> str   : Stable, LLM-friendly evidence block (no example numbers).
- build_prompt(q, cards) -> str : System+task prompt that is robust to partial evidence.
- simple_summarize(cards) -> str: Human-friendly fallback text if the LLM call fails.
"""

from __future__ import annotations

from typing import Any

# ---------- Style controls ----------
# Single ASCII tag to mark problems everywhere (matches our generator plan)
ISSUE_TAG = "[issue]"
# Simple hedging linter list (model instruction only; we don't change evidence)
_FORBID_HEDGES = ["suggests", "indicates", "implies", "potentially", "could", "might"]


def pack_context(cards: list[dict[str, Any]]) -> str:
    """Compact, authoritative listing of evidence items for the LLM.

    Notes
    -----
    - Emits a single `counts:` line when present; this is the only numeric source of truth.
    - Avoids illustrative examples that could leak incorrect numbers into the model.
    """
    lines: list[str] = []
    for c in cards:
        meta = (c.get("metadata") or {}) if isinstance(c.get("metadata"), dict) else {}
        hint = (
            (meta.get("structured_hint") or {})
            if isinstance(meta.get("structured_hint"), dict)
            else {}
        )

        observation = hint.get("observation") or ""
        implication = hint.get("implication") or ""
        recommendation = hint.get("recommendation") or ""

        pid = c.get("probe_id") or c.get("doc_id", "<unknown>")
        mml = c.get("mml")
        title = c.get("title") or pid
        domain = meta.get("domain")
        severity = meta.get("severity")
        status = meta.get("status")

        header_bits = [f"[{pid}]"]
        if mml is not None:
            header_bits.append(f"MML-{mml}")
        if domain:
            header_bits.append(str(domain))
        if severity:
            header_bits.append(f"severity={severity}")
        # Normalize status presentation to align with ISSUE_TAG
        if status:
            header_bits.append(
                ISSUE_TAG if str(status).lower() == "issue" else f"status={status}"
            )

        lines.append(" ".join(header_bits))
        lines.append(f"  title: {title}")

        # Canonical numeric source (authoritative)
        counts = meta.get("counts")
        if isinstance(counts, dict) and counts:
            flat = ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
            lines.append(f"  counts: {flat}")

        if observation:
            lines.append(f"  observation: {observation}")
        if implication:
            lines.append(f"  implication: {implication}")
        if recommendation:
            lines.append(f"  recommendation: {recommendation}")

        lines.append("")  # blank line between items

    return "\n".join(lines).strip()


def build_prompt(question: str, cards: list[dict[str, Any]]) -> str:
    """Construct a prompt that is honest about partial evidence and grounded in citations.

    Output sections (use these headings verbatim, order surfaces actions early):
     1) Maturity Summary
     2) Key Findings and Fixes
     3) Gaps in Evidence
     4) Optional: Viability/Alignment Note
    """
    context_block = pack_context(cards)

    system_instructions = """
SYSTEM PROMPT — RAG-First, Representation-First Maturity

You are an expert systems engineer. Answer the USER QUESTION strictly from the provided EVIDENCE.
You are judging the model's *representation maturity*, not the solution's viability.

Core rules
- Ground every claim in EVIDENCE; cite the source as [probe_id].
- Be direct. State facts from the evidence, then clearly explain their impact.
- Do not invent numbers or scope.
- **Use Markdown for formatting**:
  - Use `##` for all headings (e.g., `## Maturity Summary`).
  - Use `**bold**` for the key labels: **Fact**, **Impact**, and **Fix**.

Output format (use these headings verbatim)

## Maturity Summary
- 1–2 sentences: a blunt, direct summary of the model's maturity based *only* on the provided evidence.

## Key Findings and Fixes
- A bulleted list of the issues or "ok" findings from the EVIDENCE.
- **This section is ONLY for items found in the EVIDENCE block.**
- **Do NOT** add general maturity advice (like 'code reviews' or 'testing') if it is not explicitly in the EVIDENCE.
- For each finding, use this exact 3-line template:
  - [probe_id] [issue/ok]: **Fact:** <The observation from the evidence>.
    - **Impact:** <The implication from the evidence>.
    - **Fix:** <The recommendation from the evidence>.
- If all evidence items are `status=pass`, state that no issues were found in this evidence.

## Gaps in Evidence
- **This is the ONLY section for missing information.**
- State that the analysis is limited to the retrieved evidence.
- List any maturity areas (like 'documentation quality', 'testing') that the USER QUESTION asked about but were **not** present in the EVIDENCE.

## Optional: Viability/Alignment Note (non-scored)
- If the design looks questionable (even if the model is mature), note it briefly here.
""".strip()

    # We must wrap the prompt in Mistral's instruction template.
    # The pre-fill `## Maturity Summary` now goes *after* the [/INST] tag.

    prompt = (
        f"<s>[INST] {system_instructions.format(issue_tag=ISSUE_TAG)}\n\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        f"EVIDENCE:\n{context_block}\n"
        f"[/INST]\n"
        f"## Maturity Summary"
    )

    return prompt


def simple_summarize(cards: list[dict[str, Any]]) -> str:
    """Human-friendly fallback if the LLM step fails."""
    titles = [c.get("title") for c in cards if c.get("title")]
    head = f"Found {len(cards)} evidence cards in scope."
    if titles:
        head += " Example items:\n- " + "\n- ".join(titles[:5])
    return head + (
        "\n\nThe AI explanation step failed; review the evidence above and first address the clearest"
        " representation gaps (e.g., traceability breaks, unclear naming, missing interfaces)."
    )
