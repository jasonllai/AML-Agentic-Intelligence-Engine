"""Schema validation tests."""

import pytest
from pydantic import ValidationError

from app.agents.router import route_agents
from app.agents.state import initial_state
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.roles import SupportedRole


def test_analysis_request_accepts_supported_role_and_task() -> None:
    """Analysis requests should validate supported roles and tasks."""
    request = AnalysisRequest(
        role=SupportedRole.DATA_SCIENTIST,
        task_type="feature_quality_review",
        query="Critique the velocity features for customer C-123.",
    )

    assert request.role == SupportedRole.DATA_SCIENTIST
    assert request.require_full_report is False


def test_analysis_request_rejects_unknown_task_type() -> None:
    """Unsupported task types should fail validation."""
    with pytest.raises(ValidationError):
        AnalysisRequest(
            role=SupportedRole.INVESTIGATOR,
            task_type="unsupported_task",
            query="Review this alert.",
        )


def test_analysis_response_shape() -> None:
    """Analysis responses should carry run and governance metadata."""
    response = AnalysisResponse(
        run_id="run-1",
        role=SupportedRole.MODEL_VALIDATOR,
        executed_agents=["model_explanation_agent"],
        status="completed",
        result={"summary": "stub"},
        guardrail_status="passed",
        judge_scores={"groundedness": 0.8},
        route_explanation="test route",
    )

    assert response.judge_scores == {"groundedness": 0.8}


def test_router_uses_selected_agents_when_provided() -> None:
    """Explicit agent selection should override default role routing."""
    assert route_agents(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        selected_agents=[" typology_mapping_agent ", ""],
    ) == ["typology_mapping_agent", "guardrail_agent"]


def test_initial_state_contains_required_collections() -> None:
    """Initial graph state should include mutable collection fields."""
    state = initial_state(
        role=SupportedRole.COMPLIANCE_STRATEGY,
        task_type="full_intelligence_report",
        query="Generate a governed report.",
    )

    assert state["retrieved_documents"] == []
    assert state["agent_outputs"] == {}
    assert state["guardrail_flags"] == []
