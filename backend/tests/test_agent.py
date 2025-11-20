import httpx

"""Test script to interact with the Agent API endpoint."""

url = "http://localhost:8000/api/chat"
payload = {
    "history": [
        {"role": "user", "content": "What is the status of the maturity check?"}
    ]
}

print("Asking Agent...")
# Use a context manager for better performance
with httpx.Client(timeout=180.0) as client:
    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"\nResponse:\n{result['content']}")
    except Exception as e:
        print(f"Error: {e}")
