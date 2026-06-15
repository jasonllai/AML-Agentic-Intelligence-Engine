"""Structured output schemas for AML LLM-backed agents."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class EvidenceItem(BaseModel):
    """Traceable evidence item used in agent outputs and reports."""

    source: str
    reference: str
    description: str
    value: Any | None = None


class Citation(BaseModel):
    """Citation to a retrieved AML knowledge document."""

    doc_id: str
    title: str
    source: str
    url: str | None = None


class TransactionBehaviourOutput(BaseModel):
    """Structured transaction behaviour analysis."""

    behavioural_summary: str
    abnormal_patterns: list[str] = Field(default_factory=list)
    baseline_comparison: str
    key_features: dict[str, str] = Field(default_factory=dict)
    uncertainty: str
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class ModelExplanationOutput(BaseModel):
    """Structured model explanation output."""

    model_summary: str
    top_risk_drivers: list[str] = Field(default_factory=list)
    score_interpretation: str
    model_uncertainty: str
    feature_directionality: dict[str, str] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_uncertainty_language(self) -> "ModelExplanationOutput":
        """Require language that avoids treating scores as proof."""
        combined = " ".join([self.score_interpretation, self.model_uncertainty, *self.caveats]).lower()
        if "not proof" not in combined and "not evidence of suspicious activity by itself" not in combined:
            raise ValueError("Model explanation must state that the score is not proof of suspicious activity.")
        return self


class CandidateExplanationOutput(BaseModel):
    """LLM-organized explanation for one deterministic model candidate."""

    summary: str
    model_reasoning: str
    feature_driver_explanation: str
    suggested_investigator_focus: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TypologyMappingOutput(BaseModel):
    """Structured typology mapping output."""

    matched_typologies: list[str] = Field(default_factory=list)
    supporting_indicators: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    careful_language_summary: str

    @model_validator(mode="after")
    def enforce_careful_language(self) -> "TypologyMappingOutput":
        """Block prohibited conclusory AML language."""
        prohibited = ("the customer is laundering money", "file an str", "criminal activity confirmed")
        summary = self.careful_language_summary.lower()
        if any(phrase in summary for phrase in prohibited):
            raise ValueError("Typology output used prohibited conclusory language.")
        required = (
            "resembles indicators associated with",
            "may warrant further review",
            "evidence is insufficient to conclude",
        )
        if not any(phrase in summary for phrase in required):
            raise ValueError("Typology output must use careful, non-conclusive language.")
        return self


class RecommendedPySparkFeature(BaseModel):
    """Feature recommendation with implementation guidance."""

    feature_name: str
    business_rationale: str
    formula_description: str
    required_columns: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    leakage_risk: str
    expected_direction: str
    pyspark_pseudocode: str


class FeatureCriticOutput(BaseModel):
    """Structured feature quality critique."""

    feature_quality_findings: list[str] = Field(default_factory=list)
    unstable_features: list[str] = Field(default_factory=list)
    possible_leakage_risks: list[str] = Field(default_factory=list)
    missing_feature_opportunities: list[str] = Field(default_factory=list)
    recommended_pyspark_features: list[RecommendedPySparkFeature] = Field(min_length=1)
    validation_tests: list[str] = Field(default_factory=list)


class EvidenceAssemblyOutput(BaseModel):
    """Structured final report output."""

    report_markdown: str
    included_sections: list[str] = Field(default_factory=list)
    evidence_table: list[dict[str, Any]] = Field(default_factory=list)
    limitations_and_uncertainty: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class JudgePanelOutput(BaseModel):
    """Structured judge scoring output."""

    groundedness: float = Field(..., ge=0.0, le=1.0)
    coverage: float = Field(..., ge=0.0, le=1.0)
    governance_readiness: float = Field(..., ge=0.0, le=1.0)
    rationale: str


class GuardrailReviewOutput(BaseModel):
    """Structured compliance guardrail review."""

    status: str
    flags: list[str] = Field(default_factory=list)
    safe_summary: str
    required_disclaimers: list[str] = Field(default_factory=list)
