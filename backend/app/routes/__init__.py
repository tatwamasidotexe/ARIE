"""API routes."""
from fastapi import APIRouter
from app.routes import insights, trends, reports

api_router = APIRouter()
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(trends.router, prefix="/trends", tags=["trends"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
