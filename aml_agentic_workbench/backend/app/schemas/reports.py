"""Report request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.roles import SupportedRole


class ReportStatusResponse(BaseModel):
    """Report generation status."""

    report_id: str
    status: str
    created_at: datetime | None = None


class ReportSummary(BaseModel):
    """Governed AML intelligence report summary."""

    run_id: str
    title: str
    role: SupportedRole
    task_type: str
    status: str
    overall_judge_score: float | None = None
    guardrail_status: str
    created_at: datetime


class ReportDetailResponse(BaseModel):
    """Detailed report and run output for the workbench UI."""

    run_id: str
    role: SupportedRole
    task_type: str
    status: str
    guardrail_status: str
    final_report: str | None = None
    executed_agents: list[str] = Field(default_factory=list)
    judge_scores: dict[str, float] | None = None
    route_explanation: str | None = None
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    audit_trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ReportListResponse(BaseModel):
    """Report history response."""

    reports: list[ReportSummary]
