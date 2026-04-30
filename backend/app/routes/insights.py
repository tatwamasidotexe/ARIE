"""Insight query endpoints."""
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import InsightReportOut, SearchQuery
from app.repositories import list_insights, get_insight_by_id, search_insights_by_problem

router = APIRouter()


@router.get("", response_model=List[InsightReportOut])
def query_insights(
    limit: int = 20,
    min_confidence: Optional[float] = None,
    db: Session = Depends(get_db),
    source: Optional[str] = None, 
):
    """List insights with optional confidence filter."""
    reports = list_insights(db, limit=limit, min_confidence=min_confidence)
    return reports


@router.get("/search", response_model=List[InsightReportOut])
def search_insights(
    q: str,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Search insights by problem summary."""
    if not q.strip():
        return []
    reports = search_insights_by_problem(db, q, limit=limit)
    return reports


@router.get("/{report_id}", response_model=InsightReportOut)
def get_insight(
    report_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single insight report by ID."""
    report = get_insight_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Insight not found")
    return report
