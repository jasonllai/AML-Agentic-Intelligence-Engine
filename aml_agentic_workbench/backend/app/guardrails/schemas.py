"""Guardrail and approval schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field


class GuardrailStatus(StrEnum):
    """Policy decision status."""

    PASSED = "passed"
    FAILED = "failed"
    REWRITTEN = "rewritten"


class GuardrailDecision(BaseModel):
    """Structured guardrail decision."""

    status: GuardrailStatus
    allowed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    safe_output: str | None = None
    audit_only_output: str | None = None


class ApprovalStatus(StrEnum):
    """Approval state for sensitive actions."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalDecision(BaseModel):
    """Approval requirement decision."""

    action: str
    status: ApprovalStatus
    reason: str | None = None

