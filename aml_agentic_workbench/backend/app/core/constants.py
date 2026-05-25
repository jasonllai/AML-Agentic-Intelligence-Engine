"""Shared constants for the AML workbench."""

SUPPORTED_TASK_TYPES: tuple[str, ...] = (
    "customer_behaviour_analysis",
    "model_risk_explanation",
    "typology_mapping",
    "feature_quality_review",
    "full_intelligence_report",
    "investigator_summary",
    "model_validation_review",
    "compliance_typology_review",
)

DEFAULT_AGENT_STATUS = "stubbed"
GUARDRAIL_STATUS_PASSED = "passed"
