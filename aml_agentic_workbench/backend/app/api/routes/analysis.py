"""Analysis orchestration endpoints."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.agents.graph import execute_graph
from app.agents.router import RoleAwareRouter, RouteValidationError
from app.agents.state import initial_state
from app.guardrails.policy_engine import PolicyEngine
from app.rag.pgvector_store import RagStoreUnavailable
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.run_logger import AgentRunLogger
from app.services.run_store import run_store

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisResponse)
async def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Create an analysis run through the dynamically routed LangGraph workflow."""
    policy_engine = PolicyEngine()
    input_decision = policy_engine.evaluate_input(request.query, customer_id=request.customer_id, actor="system")
    if not input_decision.allowed:
        raise HTTPException(status_code=400, detail=input_decision.safe_output or "Request blocked by input policy.")

    router_service = RoleAwareRouter()
    try:
        route = router_service.route(
            role=request.role,
            task_type=request.task_type,
            query=request.query,
            selected_agents=request.selected_agents,
        )
    except RouteValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    run_id = str(uuid4())
    state = initial_state(
        role=request.role,
        task_type=request.task_type,
        query=request.query,
        customer_id=request.customer_id,
        run_id=run_id,
        alert_id=request.alert_id,
        route=route.agents,
        route_explanation=router_service.explain_route(route),
    )
    try:
        final_state = execute_graph(route, state)
    except RagStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "pgvector RAG store is not initialized or unavailable" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise
    final_report = final_state.get("final_report") or ""
    citations = _collect_citations(final_state)
    policy_context = {
        "transactions": final_state.get("transaction_summary"),
        "model_outputs": final_state.get("model_outputs"),
        "documents": final_state.get("retrieved_documents", []),
        "citations": citations,
        "agent_outputs": final_state.get("agent_outputs", {}),
    }
    judge_result, output_decision = policy_engine.evaluate_output(
        output=final_report,
        context=policy_context,
        citations=citations,
    )
    if not output_decision.allowed:
        final_state["audit_trace"] = [
            *final_state.get("audit_trace", []),
            {
                "event": "guardrail_failed",
                "failure_reasons": output_decision.failure_reasons,
                "unsafe_output_stored_for_audit_only": bool(output_decision.audit_only_output),
            },
        ]
        final_report = output_decision.safe_output or (
            "Output blocked by AML policy. Evidence is insufficient to conclude; requires human review before action."
        )
        final_state["final_report"] = final_report

    AgentRunLogger().create_run_record(
        run_id=run_id,
        role=request.role.value,
        task_type=request.task_type,
        query=request.query,
        customer_id=request.customer_id,
        alert_id=request.alert_id,
        route=route.agents,
        route_explanation=route.explanation,
    )
    AgentRunLogger().create_step_records(run_id, final_state)

    guardrail_flags = [*final_state.get("guardrail_flags", []), *output_decision.flags]
    result = {
        "message": "Dynamic AML agent route executed with policy and judge evaluation.",
        "query": request.query,
        "require_full_report": request.require_full_report,
        "agent_outputs": final_state.get("agent_outputs", {}),
        "final_report": final_report,
        "audit_trace": final_state.get("audit_trace", []),
        "judge_panel": judge_result.model_dump(mode="json"),
        "guardrail_failure_reasons": output_decision.failure_reasons,
    }
    response = AnalysisResponse(
        run_id=run_id,
        role=request.role,
        executed_agents=final_state.get("executed_agents", []),
        status="completed" if output_decision.allowed else "guardrail_failed",
        result=result,
        guardrail_status="failed" if guardrail_flags or not output_decision.allowed else "passed",
        judge_scores={criterion.value: decision.score for criterion, decision in judge_result.decisions.items()}
        | {"overall_score": judge_result.overall_score},
        route_explanation=route.explanation,
    )
    run_store.add(response, task_type=request.task_type)
    return response


def _collect_citations(state: dict) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for output in state.get("agent_outputs", {}).values():
        citations.extend(output.get("citations", []))
    return citations
