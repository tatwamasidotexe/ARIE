"""Report viewing endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import InsightReportOut
from app.repositories import get_insight_by_id

router = APIRouter()


@router.get("/{report_id}", response_model=InsightReportOut)
def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
):
    """Get full report by ID."""
    report = get_insight_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
