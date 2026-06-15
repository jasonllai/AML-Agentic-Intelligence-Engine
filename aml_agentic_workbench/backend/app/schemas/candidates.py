"""Schemas for model-driven AML candidate handoff and investigator feedback."""

from typing import Any, Literal

from pydantic import BaseModel, Field

DETECTION_CANDIDATE_DISCLAIMER = (
    "This model output is used for AML investigation prioritization only. "
    "It is not proof of suspicious activity and does not by itself support an STR decision."
)


class FeatureDriver(BaseModel):
    """Feature contribution context for a ranked AML candidate."""

    feature_name: str
    value: float | int | str | None = None
    baseline: float | int | str | None = None
    direction: str = "elevated"
    explanation: str
    feature_display_name: str | None = None
    feature_definition: str | None = None
    engineering_formula: str | None = None
    customer_value: float | int | str | None = None
    population_baseline: float | int | str | None = None
    z_score: float | None = None
    shap_value: float | None = None
    shap_direction: str | None = None
    reconstruction_contribution: float | None = None
    investigator_interpretation: str | None = None
    suggested_evidence_to_review: str | None = None
    explanation_method: str | None = None


class CandidateExplanation(BaseModel):
    """Guarded explanation text for one model-ranked candidate."""

    summary: str
    model_reasoning: str
    feature_driver_explanation: str
    suggested_investigator_focus: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DetectionCandidatePackage(BaseModel):
    """Investigator-ready package produced by AML data science scoring."""

    candidate_id: str
    customer_id: str
    model_run_id: str
    model_version: str
    model_family: str
    rank: int = Field(..., ge=1)
    score: float = Field(..., ge=0.0, le=1.0)
    score_percentile: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(..., ge=0.0, le=1.0)
    threshold_reason: str
    alert_recommendation: str
    top_feature_drivers: list[FeatureDriver] = Field(default_factory=list)
    model_specific_driver_details: list[dict[str, Any]] = Field(default_factory=list)
    feature_driver_explanations: list[str] = Field(default_factory=list)
    llm_explanation: CandidateExplanation | None = None
    guardrail_status: Literal["passed", "fallback_used", "llm_unavailable", "not_generated"] = "not_generated"
    guardrail_flags: list[str] = Field(default_factory=list)
    fallback_explanation: CandidateExplanation | None = None
    supporting_transaction_slices: list[dict[str, Any]] = Field(default_factory=list)
    peer_group_baseline: dict[str, Any] = Field(default_factory=dict)
    model_limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    suggested_investigation_focus: list[str] = Field(default_factory=list)
    disclaimer: str = DETECTION_CANDIDATE_DISCLAIMER


class InvestigatorFeedback(BaseModel):
    """Structured feedback returned from investigation to model monitoring."""

    case_disposition: Literal["close", "monitor", "escalate", "prepare_reportable_suspicion"]
    typology_assessment: str
    false_positive_reason: str | None = None
    useful_model_drivers: list[str] = Field(default_factory=list)
    misleading_model_drivers: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    investigator_notes: str
    label_for_model_evaluation: Literal["true_concern", "false_positive", "needs_review", "insufficient_information"]
