"""Evaluation and judge schemas."""

from pydantic import BaseModel, Field


class JudgeScore(BaseModel):
    """Single judge score for an agent or final report."""

    criterion: str
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str | None = None


class EvaluationResult(BaseModel):
    """Evaluation bundle produced by mock or real judges."""

    scores: list[JudgeScore]
    overall_score: float = Field(..., ge=0.0, le=1.0)

