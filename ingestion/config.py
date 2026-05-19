"""Ingestion configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")