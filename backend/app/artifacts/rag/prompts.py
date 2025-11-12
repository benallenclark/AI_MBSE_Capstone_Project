# ------------------------------------------------------------
# Module: backend/app/assist/prompt_builder.py
# Purpose: Build context-rich prompts and summaries for MBSE maturity analysis.
# ------------------------------------------------------------

"""Helpers for generating analysis prompts and summaries for MBSE maturity tasks.

This module constructs textual prompts for model-based systems engineering
assistants, combining user questions with evidence cards for context.

Responsibilities
----------------
- Build structured natural language prompts combining questions and evidence cards.
- Summarize available evidence for quick human-readable insights.
- Limit context length for efficient model consumption.
- Encourage actionable, evidence-based responses in generated outputs.
"""

from __future__ import annotations


def build_prompt(question: str, cards: list[dict]) -> str:
    """Construct a structured LLM prompt from a question and evidence cards.

    Parameters
    ----------
    question : str
        The user's question or analytical task.
    cards : list of dict
        Evidence cards containing at least `doc_id`, `title`, and `body_text` or `body`.

    Returns
    -------
    str
        A formatted prompt ready for LLM completion.

    Notes
    -----
    - Only the first 8 cards are included for brevity.
    - Falls back gracefully if `title` or `body_text` is missing.
    - Encourages concise, evidence-cited, and action-oriented answers.
    """
    N = 8
    parts: list[str] = []
    for c in cards[:N]:
        title = c.get("title") or c.get("doc_id") or "Card"
        body = c.get("body_text") or c.get("body") or ""
        parts.append(f"Title: {title}\nBody: {body}")
    context = "\n\n".join(parts)
    return (
        "You are an MBSE maturity assistant.\n\n"
        f"Question:\n{question}\n\n"
        "Evidence (cards):\n"
        f"{context}\n\n"
        "Respond with a brief, concrete answer that cites specific findings from the evidence above and suggests next steps."
    )


def simple_summarize(cards: list[dict]) -> str:
    """Generate a quick summary of available evidence cards.

    Parameters
    ----------
    cards : list of dict
        Evidence card data, ideally including `title` fields.

    Returns
    -------
    str
        Human-readable summary text suitable for display or reporting.

    Notes
    -----
    - Includes up to 5 example titles for quick orientation.
    - Always ends with actionable MBSE improvement hints.
    """
    titles = [c.get("title") for c in cards if c.get("title")]
    head = f"Found {len(cards)} evidence cards in scope."
    if titles:
        head += " Example items:\n- " + "\n- ".join(titles[:5])
    return head + (
        "\n\nStart by fixing high-impact hygiene: type all ports, remove unused elements, add missing requirement links, and resolve duplicate names."
    )
