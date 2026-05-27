import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Load from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://arie:arie@localhost:5432/arie")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Return a new SQLAlchemy session bound to the shared process-level engine."""
    return SessionLocal()


def get_engine():
    """Return the shared process-level SQLAlchemy engine."""
    return engine


@contextmanager
def db_session():
    """Context manager for scripts that want automatic session cleanup."""
    db = get_db()
    try:
        yield db
    finally:
        db.close()
