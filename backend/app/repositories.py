"""Data access layer for queries."""
from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app.models import RawPost, Document, Problem, InsightReport


def get_insight_by_id(db: Session, report_id: UUID) -> Optional[InsightReport]:
    return db.query(InsightReport).filter(InsightReport.id == report_id).first()


def list_insights(
    db: Session,
    limit: int = 20,
    min_confidence: Optional[float] = None,
) -> List[InsightReport]:
    q = db.query(InsightReport).order_by(desc(InsightReport.created_at))
    if min_confidence is not None:
        q = q.filter(InsightReport.confidence_score >= min_confidence)
    return q.limit(limit).all()


def search_insights_by_problem(db: Session, query: str, limit: int = 20) -> List[InsightReport]:
    return (
        db.query(InsightReport)
        .join(Problem, InsightReport.problem_id == Problem.id)
        .filter(Problem.summary.ilike(f"%{query}%"))
        .order_by(desc(InsightReport.confidence_score))
        .limit(limit)
        .all()
    )


def list_problems(
    db: Session,
    limit: int = 20,
    min_frequency: Optional[float] = None,
) -> List[Problem]:
    q = db.query(Problem).order_by(desc(Problem.frequency_score))
    if min_frequency is not None:
        q = q.filter(Problem.frequency_score >= min_frequency)
    return q.limit(limit).all()


def get_problem_with_report(db: Session, problem_id: UUID) -> Optional[Problem]:
    return db.query(Problem).filter(Problem.id == problem_id).first()


def get_latest_report_for_problem(db: Session, problem_id: UUID) -> Optional[InsightReport]:
    return (
        db.query(InsightReport)
        .filter(InsightReport.problem_id == problem_id)
        .order_by(desc(InsightReport.created_at))
        .first()
    )
