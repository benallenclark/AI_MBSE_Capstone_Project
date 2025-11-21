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
    messages = [
        {
            "role": "system",
            "content": (
                "You are a function calling AI model. You are an expert Systems Engineering Assistant "
                "analyzing a Cameo model. You have access to a graph database via the provided tools. "
                "Don't make assumptions about the model structure; always verify using 'query_graph' "
                "or 'check_maturity_status' before answering. "
                "If you find a violation, cite the specific ID and Element Name. "
                "Always provide a natural language response to the user, not raw tool results."
            ),
        }
    ] + history

    print(f"Sending request to {OLLAMA_MODEL}...")

    # 2. First Pass: Ask the LLM
    response = client.chat.completions.create(
        model=OLLAMA_MODEL, 
        messages=messages, 
        tools=TOOLS_SCHEMA, 
        tool_choice="auto"
    )

    message = response.choices[0].message
    
    # 3. Check for Tool Calls
    if message.tool_calls:
        print(f"Model requested {len(message.tool_calls)} tool(s)")

        # Add the model's response (with tool calls) to history
        # Convert to dict format for serialization
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        })

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
            print(f"Tool result: {result[:200]}...")  # Debug: show first 200 chars

            # Feed the result back to the LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

        # 4. Second Pass: Get Final Answer based on Tool Results
        print("Getting final response after tool execution...")
        final_response = client.chat.completions.create(
            model=OLLAMA_MODEL, 
            messages=messages
        )
        
        final_message = final_response.choices[0].message
        content = final_message.content
        
        if not content or not str(content).strip():
            # Fallback - this shouldn't happen with Hermes 3
            print("WARNING: Model returned empty content after tool use")
            return "(The model did not provide a response. Please try rephrasing your question.)"
        
        print(f"Final response: {str(content)[:200]}...")
        return str(content).strip()

    # If no tools were used, just return the text
    content = message.content or ""
    if not str(content).strip():
        return "(no content returned by model)"
    
    return str(content).strip()