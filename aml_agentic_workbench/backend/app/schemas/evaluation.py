"""Evaluation and judge schemas."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.roles import SupportedRole


class JudgeScore(BaseModel):
    """Single judge score for an agent or final report."""

    criterion: str
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str | None = None


class EvaluationResult(BaseModel):
    """Evaluation bundle produced by mock or real judges."""

    scores: list[JudgeScore]
    overall_score: float = Field(..., ge=0.0, le=1.0)


class GoldenCase(BaseModel):
    """One generated system-evaluation case."""

    case_id: str
    role: SupportedRole
    task_type: str
    customer_id: str | None = None
    query: str
    expected_agents: list[str]
    expected_evidence: list[str] = Field(default_factory=list)
    expected_guardrail_outcome: str = Field(pattern="^(allowed|blocked)$")
    requires_citations: bool = False
    tags: list[str] = Field(default_factory=list)


class EvaluationCaseResult(BaseModel):
    """Evaluation result for one golden case."""

    case_id: str
    role: SupportedRole
    task_type: str
    query: str
    passed: bool
    metrics: dict[str, float]
    expected_agents: list[str]
    actual_agents: list[str]
    expected_guardrail_outcome: str
    actual_guardrail_outcome: str
    judge_rationale: dict[str, str] = Field(default_factory=dict)
    retrieved_citations: list[dict[str, Any]] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class EvaluationRunSummary(BaseModel):
    """Aggregate system-evaluation run result."""

    run_id: str
    status: str
    case_count: int
    passed_count: int
    failed_count: int
    overall_score: float = Field(..., ge=0.0, le=1.0)
    metrics: dict[str, float]
    cases: list[EvaluationCaseResult]
    created_at: str


class EvaluationRunRequest(BaseModel):
    """Request to execute a generated evaluation suite."""

    case_limit: int = Field(default=20, ge=1, le=500)


class GoldenDatasetRequest(BaseModel):
    """Request to generate a golden dataset."""

    case_limit: int = Field(default=100, ge=1, le=1000)


class GoldenDatasetResponse(BaseModel):
    """Response after generating golden evaluation cases."""

    case_count: int
    cases: list[GoldenCase]
