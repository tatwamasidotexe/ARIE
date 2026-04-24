"""SQLAlchemy models matching database schema."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector
    _embedding_col = Vector(1536)
except ImportError:
    _embedding_col = Column("embedding", JSONB)

from app.database import Base


class RawPost(Base):
    __tablename__ = "raw_posts"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    source = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False, unique=True)
    title = Column(Text, nullable=False)
    content = Column(Text)
    url = Column(Text)
    author = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    extra_metadata = Column("metadata", JSONB, default=dict)


class Document(Base):
    __tablename__ = "documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    raw_post_id = Column(PGUUID(as_uuid=True), ForeignKey("raw_posts.id", ondelete="CASCADE"))
    source = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    embedding = _embedding_col
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    extra_metadata = Column("metadata", JSONB, default=dict)


class Problem(Base):
    __tablename__ = "problems"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    summary = Column(Text, nullable=False)
    frequency_score = Column(Float, default=0)
    document_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    first_detected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    status = Column(String(50), default="detected")


class InsightReport(Base):
    __tablename__ = "insight_reports"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    problem_id = Column(PGUUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"))
    problem_summary = Column(Text, nullable=False)
    evidence = Column(JSONB, default=list)
    root_causes = Column(JSONB, default=list)
    solutions = Column(JSONB, default=list)
    confidence_score = Column(Float, nullable=False)
    sources = Column(JSONB, default=list)
    governance_checks = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
