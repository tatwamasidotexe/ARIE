"""Application configuration."""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://arie:arie@localhost:5432/arie"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ARIE/1.0"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
