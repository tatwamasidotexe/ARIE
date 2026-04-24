"""Pydantic schemas for API requests/responses."""
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class InsightReportOut(BaseModel):
    id: UUID
    problem_id: UUID
    problem_summary: str
    evidence: List[Any] = []
    root_causes: List[Any] = []
    solutions: List[Any] = []
    confidence_score: float
    sources: List[Any] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ProblemOut(BaseModel):
    id: UUID
    summary: str
    frequency_score: float
    status: str
    first_detected_at: datetime
    last_updated_at: datetime

    class Config:
        from_attributes = True


class ProblemWithReport(ProblemOut):
    latest_report: Optional[InsightReportOut] = None


class SearchQuery(BaseModel):
    query: str
    limit: int = Field(default=20, le=100)
    min_confidence: Optional[float] = Field(default=0.0, ge=0, le=1)


class TrendQuery(BaseModel):
    limit: int = Field(default=10, le=50)
    min_frequency: Optional[float] = Field(default=0.0)
