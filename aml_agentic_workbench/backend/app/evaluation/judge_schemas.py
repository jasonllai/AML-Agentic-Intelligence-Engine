"""Judge contracts for LLM-as-judge evaluation."""

from enum import StrEnum

from pydantic import BaseModel, Field


class JudgeSeverity(StrEnum):
    """Severity assigned to detected judge issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JudgeCriterion(StrEnum):
    """Supported judge criteria."""

    FAITHFULNESS = "faithfulness"
    CITATION = "citation"
    TYPOLOGY = "typology"
    DATA_SCIENCE = "data_science"
    COMPLIANCE = "compliance"
    USEFULNESS = "usefulness"
    ANSWER_RELEVANCE = "answer_relevance"


class JudgeDecision(BaseModel):
    """Standard output from every judge."""

    criterion: JudgeCriterion
    score: float = Field(..., ge=0.0, le=1.0)
    pass_fail: str = Field(pattern="^(pass|fail)$")
    explanation: str
    detected_issues: list[str] = Field(default_factory=list)
    recommended_fix: str | None = None
    severity: JudgeSeverity = JudgeSeverity.LOW


class JudgePanelResult(BaseModel):
    """Aggregated judge panel result."""

    decisions: dict[JudgeCriterion, JudgeDecision]
    overall_score: float = Field(..., ge=0.0, le=1.0)
    pass_fail: str = Field(pattern="^(pass|fail)$")
    failure_reason: str | None = None
