"""Workflow configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://arie:arie@localhost:5432/arie")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_NEW_POST = "arie:events:new_post"
CONSUMER_GROUP = "arie-workers"
CONSUMER_NAME = "worker-1"
