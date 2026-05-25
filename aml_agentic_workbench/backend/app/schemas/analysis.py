"""Request and response schemas for AML analysis runs."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.constants import SUPPORTED_TASK_TYPES
from app.schemas.roles import SupportedRole


class AnalysisRequest(BaseModel):
    """Client request for a role-aware AML analysis run."""

    role: SupportedRole
    task_type: str = Field(..., min_length=1)
    customer_id: str | None = None
    alert_id: str | None = None
    query: str = Field(..., min_length=1, max_length=8000)
    selected_agents: list[str] | None = None
    require_full_report: bool = False

    @model_validator(mode="after")
    def validate_task_type(self) -> "AnalysisRequest":
        """Ensure task types stay inside the supported catalog."""
        if self.task_type not in SUPPORTED_TASK_TYPES:
            allowed = ", ".join(SUPPORTED_TASK_TYPES)
            raise ValueError(f"Unsupported task_type '{self.task_type}'. Expected one of: {allowed}.")
        return self


class AnalysisResponse(BaseModel):
    """API response for an AML analysis run."""

    run_id: str
    role: SupportedRole
    executed_agents: list[str]
    status: str
    result: dict[str, Any]
    guardrail_status: str
    judge_scores: dict[str, float] | None = None
    route_explanation: str | None = None
