"""Trending problems endpoints."""
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProblemOut, ProblemWithReport
from app.repositories import list_problems, get_problem_with_report, get_latest_report_for_problem

router = APIRouter()


@router.get("", response_model=List[ProblemOut])
def list_trending_problems(
    limit: int = 10,
    min_frequency: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """List trending problems ranked by frequency."""
    problems = list_problems(db, limit=limit, min_frequency=min_frequency)
    return problems


@router.get("/{problem_id}", response_model=ProblemWithReport)
def get_problem_detail(
    problem_id: UUID,
    db: Session = Depends(get_db),
):
    """Get problem detail with latest report."""
    problem = get_problem_with_report(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    report = get_latest_report_for_problem(db, problem_id)
    return ProblemWithReport(
        **{c.key: getattr(problem, c.key) for c in problem.__table__.columns},
        latest_report=report,
    )
