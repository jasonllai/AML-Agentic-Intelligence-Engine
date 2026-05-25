"""Report endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.reports import ReportDetailResponse, ReportListResponse, ReportStatusResponse
from app.services.run_store import run_store

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_id}/status", response_model=ReportStatusResponse)
async def get_report_status(report_id: str) -> ReportStatusResponse:
    """Return a placeholder report status."""
    report = run_store.get(report_id)
    if report is None:
        return ReportStatusResponse(report_id=report_id, status="not_generated")
    return ReportStatusResponse(report_id=report_id, status=report.status, created_at=report.created_at)


@router.get("", response_model=ReportListResponse)
async def list_reports() -> ReportListResponse:
    """Return previous local analysis runs."""
    return ReportListResponse(reports=run_store.list())


@router.get("/{run_id}", response_model=ReportDetailResponse)
async def get_report(run_id: str) -> ReportDetailResponse:
    """Return a previous local analysis run report."""
    report = run_store.get(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report
