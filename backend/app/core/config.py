import os

from dotenv import load_dotenv

# Load variables from .env file (if present)
load_dotenv()

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")  # Default for dev

# Auth tuple required by the Neo4j driver
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

# LLM Config (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
OLLAMA_API_KEY = "ollama"  # Required by SDK but unused
