"""Agent configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://arie:arie@localhost:5432/arie")
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# all-MiniLM-L6-v2 outputs 384-dim embeddings
EMBEDDING_DIM = 384
LLM_MODEL = "llama-3.1-8b-instant"