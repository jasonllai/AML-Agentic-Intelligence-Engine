"""LangGraph-compatible state definitions."""

from typing import Any, TypedDict

from app.schemas.roles import SupportedRole


class AMLAgentState(TypedDict, total=False):
    """Shared state carried through the AML multi-agent graph."""

    role: SupportedRole
    task_type: str
    query: str
    run_id: str
    customer_id: str | None
    alert_id: str | None
    route: list[str]
    route_explanation: str | None
    executed_agents: list[str]
    transaction_summary: dict[str, Any] | None
    model_outputs: dict[str, Any] | None
    model_results: dict[str, list[dict[str, Any]]]
    retrieved_documents: list[dict[str, Any]]
    candidate_packages: list[dict[str, Any]]
    model_run_summary: dict[str, Any] | None
    investigation_case_review: dict[str, Any] | None
    planner_decisions: list[dict[str, Any]]
    critic_reviews: list[dict[str, Any]]
    stop_reason: str | None
    refinement_rounds: int
    stream_events: list[dict[str, Any]]
    agent_outputs: dict[str, dict[str, Any]]
    judge_outputs: dict[str, Any]
    guardrail_flags: list[str]
    final_report: str | None
    audit_trace: list[dict[str, Any]]


def initial_state(
    role: SupportedRole,
    task_type: str,
    query: str,
    customer_id: str | None = None,
    *,
    run_id: str | None = None,
    alert_id: str | None = None,
    route: list[str] | None = None,
    route_explanation: str | None = None,
) -> AMLAgentState:
    """Create an initialized graph state."""
    return AMLAgentState(
        role=role,
        task_type=task_type,
        query=query,
        run_id=run_id or "",
        customer_id=customer_id,
        alert_id=alert_id,
        route=route or [],
        route_explanation=route_explanation,
        executed_agents=[],
        transaction_summary=None,
        model_outputs=None,
        model_results={},
        retrieved_documents=[],
        candidate_packages=[],
        model_run_summary=None,
        investigation_case_review=None,
        planner_decisions=[],
        critic_reviews=[],
        stop_reason=None,
        refinement_rounds=0,
        stream_events=[],
        agent_outputs={},
        judge_outputs={},
        guardrail_flags=[],
        final_report=None,
        audit_trace=[],
    )
