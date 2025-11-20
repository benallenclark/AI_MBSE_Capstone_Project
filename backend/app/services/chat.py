import json

from openai import OpenAI

from app.core.config import OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL
from app.services.llm_tools import TOOLS_SCHEMA, execute_tool

## LLM CLIENT SETUP
client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)


def chat_with_agent(history: list):
    """
    Interacts with the Hermes 3 Agent using native tool calls.
    Args:
        history (list): The conversation history as a list of messages.
    Returns:
        str: The final response from the agent.
    """

    # 1. Setup the System Prompt (Optimized for Hermes 3)
    # Hermes 3 is "Agentic" and follows system instructions strictly.
    # We tell it to be a "function calling AI" to activate its specific training.
    messages = [
        {
            "role": "system",
            "content": (
                "You are a function calling AI model. You are an expert Systems Engineering Assistant "
                "analyzing a Cameo model. You have access to a graph database via the provided tools. "
                "Don't make assumptions about the model structure; always verify using 'query_graph' "
                "or 'check_maturity_status' before answering. "
                "If you find a violation, cite the specific ID and Element Name."
            ),
        }
    ] + history

    print(f"Sending request to {OLLAMA_MODEL}...")

    # 2. First Pass: Ask the LLM
    # Hermes 3 natively supports the 'tools' parameter via Ollama
    response = client.chat.completions.create(
        model=OLLAMA_MODEL, messages=messages, tools=TOOLS_SCHEMA, tool_choice="auto"
    )

    message = response.choices[0].message

    # 3. Check for Tool Calls
    if message.tool_calls:
        print(f"Model requested {len(message.tool_calls)} tool(s)")

        # Add the model's "intent" to history so it remembers what it asked for
        messages.append(message)

        # Execute each tool requested
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            args_json = tool_call.function.arguments

            try:
                args = json.loads(args_json)
            except json.JSONDecodeError:
                print(f"JSON Error parsing args: {args_json}")
                args = {}

            print(f"Running: {func_name}({args})")

            # EXECUTE THE PYTHON CODE
            result = execute_tool(func_name, args)

            # Feed the result back to the LLM
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": str(result)}
            )

        # 4. Second Pass: Get Final Answer based on Tool Results
        final_response = client.chat.completions.create(
            model=OLLAMA_MODEL, messages=messages
        )
        # Always coerce to a non-empty string
        msg = final_response.choices[0].message
        content = getattr(msg, "content", None)

        if not content or not str(content).strip():
            # Fallback so frontend never sees undefined/empty
            try:
                # Show something helpful for debugging
                content = json.dumps(final_response.model_dump(), indent=2)[:4000]
            except Exception:
                content = "(no content returned by model)"

        return str(content)

    # If no tools were used, just return the text
    return str(message.content or "").strip() or "(no content returned by model)"
