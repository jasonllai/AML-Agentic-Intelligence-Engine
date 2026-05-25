"""Dynamic routing and graph execution tests."""

import pytest

from app.agents.graph import DynamicGraphBuilder
from app.agents.router import (
    GUARDRAIL_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    RoleAwareRouter,
    RouteValidationError,
)
from app.agents.state import initial_state
from app.schemas.roles import SupportedRole


def test_data_scientist_model_risk_route_is_correct() -> None:
    """Data scientist model risk requests should use the prescribed route."""
    route = RoleAwareRouter().route(
        role=SupportedRole.DATA_SCIENTIST,
        task_type="model_risk_explanation",
        query="Explain the model risk for this customer.",
    )

    assert route.agents == [
        "transaction_behaviour_agent",
        "model_explanation_agent",
        "feature_critic_agent",
        "evidence_assembly_agent",
        "judge_panel_agent",
        "guardrail_agent",
    ]
    assert "data_scientist" in route.explanation


def test_selected_partial_agent_execution_appends_guardrail() -> None:
    """Selected agents should run partially with mandatory final guardrail."""
    route = RoleAwareRouter().route(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Summarize behaviour.",
        selected_agents=[TRANSACTION_BEHAVIOUR_AGENT],
    )

    assert route.is_partial is True
    assert route.agents == [TRANSACTION_BEHAVIOUR_AGENT, GUARDRAIL_AGENT]


def test_invalid_agent_selection_is_blocked() -> None:
    """Unknown or unauthorized agent selections should fail closed."""
    with pytest.raises(RouteValidationError):
        RoleAwareRouter().route(
            role=SupportedRole.COMPLIANCE_STRATEGY,
            task_type="compliance_typology_review",
            query="Map typology.",
            selected_agents=["transaction_behaviour_agent"],
        )


def test_graph_produces_final_report_for_dynamic_route() -> None:
    """Dynamic graph execution should produce a final report and executed agent list."""
    router = RoleAwareRouter()
    route = router.route(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Assess velocity spike and new counterparty burst.",
        selected_agents=["transaction_behaviour_agent", "typology_mapping_agent"],
    )
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Assess velocity spike and new counterparty burst.",
        customer_id="CUST003",
        route=route.agents,
        route_explanation=route.explanation,
    )

    final_state = DynamicGraphBuilder().run(route, state)

    assert final_state["executed_agents"] == route.agents
    assert final_state["final_report"] is not None
    assert "AML Intelligence Report" in final_state["final_report"]
    assert final_state["guardrail_flags"] == []


def test_route_explanation_is_available() -> None:
    """Router should expose an explanation for audit and API responses."""
    router = RoleAwareRouter()
    route = router.route(
        role=SupportedRole.MODEL_VALIDATOR,
        task_type="model_validation_review",
        query="Validate model risk explanation.",
    )

    assert router.explain_route(route) == route.explanation
    assert "model_validation_review" in route.explanation
