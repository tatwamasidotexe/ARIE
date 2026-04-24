"""Ingestion configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://arie:arie@localhost:5432/arie")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ARIE/1.0")

STREAM_NEW_POST = "arie:events:new_post"
