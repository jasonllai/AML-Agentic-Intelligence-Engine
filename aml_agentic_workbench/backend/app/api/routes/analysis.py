"""Analysis orchestration endpoints."""

import json
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.graph import execute_graph
from app.agents.investigator_orchestrator import (
    InvestigatorAgenticRunner,
    is_primary_investigator_agentic_request,
)
from app.agents.router import AgentRoute, RoleAwareRouter, RouteValidationError
from app.agents.state import initial_state
from app.guardrails.policy_engine import PolicyEngine
from app.rag.pgvector_store import RagStoreUnavailable
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.roles import SupportedRole
from app.services.data_service import get_data_service
from app.services.run_logger import AgentRunLogger
from app.services.run_store import run_store

router = APIRouter(prefix="/analysis", tags=["analysis"])
JUDGE_PANEL_FAILED_FLAG = "judge_panel_failed"


@router.post("", response_model=AnalysisResponse)
async def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Create an analysis run through the dynamically routed LangGraph workflow."""
    policy_engine = PolicyEngine()
    input_decision = policy_engine.evaluate_input(request.query, customer_id=request.customer_id, actor="system")
    if not input_decision.allowed:
        raise HTTPException(status_code=400, detail=input_decision.safe_output or "Request blocked by input policy.")
    _validate_investigator_customer(request)

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
        if is_primary_investigator_agentic_request(request.role, request.task_type, request.selected_agents):
            runner = InvestigatorAgenticRunner()
            for _ in runner.run(state):
                pass
            final_state = runner.state
        else:
            final_state = execute_graph(route, state)
    except RagStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "pgvector RAG store is not initialized or unavailable" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise

    return _build_analysis_response(
        request=request,
        run_id=run_id,
        route=route,
        final_state=final_state,
        policy_engine=policy_engine,
    )


@router.post("/stream")
async def create_analysis_stream(request: AnalysisRequest) -> StreamingResponse:
    """Stream a primary Investigator analysis run as server-sent events."""
    policy_engine = PolicyEngine()
    input_decision = policy_engine.evaluate_input(request.query, customer_id=request.customer_id, actor="system")
    if not input_decision.allowed:
        raise HTTPException(status_code=400, detail=input_decision.safe_output or "Request blocked by input policy.")
    _validate_investigator_customer(request)

    if not is_primary_investigator_agentic_request(request.role, request.task_type, request.selected_agents):
        raise HTTPException(
            status_code=400,
            detail="Streaming analysis is currently supported for Investigator runs only.",
        )

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

    def event_stream() -> Iterator[str]:
        runner = InvestigatorAgenticRunner()
        try:
            for event in runner.run(state):
                yield _format_sse(event["event"], event)
            response = _build_analysis_response(
                request=request,
                run_id=run_id,
                route=route,
                final_state=runner.state,
                policy_engine=policy_engine,
            )
            yield _format_sse("run_completed", {"response": response.model_dump(mode="json")})
        except Exception as exc:  # pragma: no cover - defensive stream failure path
            yield _format_sse("run_failed", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _build_analysis_response(
    *,
    request: AnalysisRequest,
    run_id: str,
    route: AgentRoute,
    final_state: dict,
    policy_engine: PolicyEngine,
) -> AnalysisResponse:
    """Build and store a response from an executed analysis state."""
    if request.task_type == "generate_model_driven_candidates":
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
        result = {
            "message": "AML model workbench generated four-model investigation candidates.",
            "query": request.query,
            "require_full_report": request.require_full_report,
            "agent_outputs": final_state.get("agent_outputs", {}),
            "model_run_summary": final_state.get("model_run_summary"),
            "model_results": final_state.get("model_results", {}),
            "model_comparison": (final_state.get("model_outputs") or {}).get("model_comparison", []),
            "candidate_packages": final_state.get("candidate_packages", []),
            "investigation_case_review": None,
            "audit_trace": final_state.get("audit_trace", []),
        }
        response = AnalysisResponse(
            run_id=run_id,
            role=request.role,
            executed_agents=final_state.get("executed_agents", []),
            status="completed",
            result=result,
            guardrail_status="passed",
            judge_scores=None,
            route_explanation=route.explanation,
        )
        run_store.add(response, task_type=request.task_type)
        return response

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
    judge_failure_reasons = _collect_judge_failure_reasons(judge_result)
    guardrail_policy_flags = [flag for flag in output_decision.flags if flag != JUDGE_PANEL_FAILED_FLAG]
    guardrail_flags = _dedupe_strings([*final_state.get("guardrail_flags", []), *guardrail_policy_flags])
    guardrail_failure_reasons = _collect_guardrail_failure_reasons(
        final_state=final_state,
        output_failure_reasons=output_decision.failure_reasons,
        judge_failure_reasons=judge_failure_reasons,
    )
    actual_guardrail_failed = bool(guardrail_flags)
    judge_warning = judge_result.pass_fail == "fail"
    governance_status = (
        "guardrail_failed" if actual_guardrail_failed else "judge_warning" if judge_warning else "passed"
    )
    judge_status = "warning" if judge_warning else "passed"

    if actual_guardrail_failed:
        final_state["audit_trace"] = [
            *final_state.get("audit_trace", []),
            {
                "event": "guardrail_failed",
                "failure_reasons": guardrail_failure_reasons,
                "unsafe_output_stored_for_audit_only": bool(output_decision.audit_only_output),
            },
        ]
        final_report = output_decision.safe_output or (
            "Output blocked by AML policy. Evidence is insufficient to conclude; requires human review before action."
        )
        final_state["final_report"] = final_report
    elif judge_warning:
        final_state["audit_trace"] = [
            *final_state.get("audit_trace", []),
            {
                "event": "judge_warning",
                "failure_reasons": judge_failure_reasons,
            },
        ]

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

    result = {
        "message": "Dynamic AML agent route executed with policy and judge evaluation.",
        "query": request.query,
        "require_full_report": request.require_full_report,
        "agent_outputs": final_state.get("agent_outputs", {}),
        "model_run_summary": final_state.get("model_run_summary"),
        "candidate_packages": final_state.get("candidate_packages", []),
        "investigation_case_review": final_state.get("investigation_case_review"),
        "planner_decisions": final_state.get("planner_decisions", []),
        "critic_reviews": final_state.get("critic_reviews", []),
        "stop_reason": final_state.get("stop_reason"),
        "refinement_rounds": final_state.get("refinement_rounds", 0),
        "guardrail_remediation_rounds": final_state.get("guardrail_remediation_rounds", 0),
        "guardrail_remediations": final_state.get("guardrail_remediations", []),
        "governance_status": governance_status,
        "judge_status": judge_status,
        "final_report": final_report,
        "audit_trace": final_state.get("audit_trace", []),
        "judge_panel": judge_result.model_dump(mode="json"),
        "guardrail_failure_reasons": guardrail_failure_reasons,
        "judge_failure_reasons": judge_failure_reasons,
    }
    response = AnalysisResponse(
        run_id=run_id,
        role=request.role,
        executed_agents=final_state.get("executed_agents", []),
        status="guardrail_failed" if actual_guardrail_failed else "completed",
        result=result,
        guardrail_status="failed" if actual_guardrail_failed else "passed",
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


def _collect_judge_failure_reasons(judge_result: object) -> list[str]:
    reasons: list[str] = []
    failure_reason = getattr(judge_result, "failure_reason", None)
    if failure_reason:
        reasons.append(str(failure_reason))
    decisions = getattr(judge_result, "decisions", {})
    for criterion, decision in decisions.items():
        if getattr(decision, "pass_fail", "pass") != "fail":
            continue
        label = getattr(criterion, "value", str(criterion))
        issues = getattr(decision, "detected_issues", []) or []
        if issues:
            reasons.extend([f"{label}: {issue}" for issue in issues])
        else:
            reasons.append(f"{label}: judge failed")
    return _dedupe_strings(reasons)


def _collect_guardrail_failure_reasons(
    *,
    final_state: dict,
    output_failure_reasons: list[str],
    judge_failure_reasons: list[str],
) -> list[str]:
    excluded = {JUDGE_PANEL_FAILED_FLAG, *judge_failure_reasons}
    reasons = [*final_state.get("guardrail_failure_reasons", []), *output_failure_reasons]
    return _dedupe_strings([reason for reason in reasons if reason not in excluded])


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _validate_investigator_customer(request: AnalysisRequest) -> None:
    """Fail closed for investigator requests that do not match real customer data."""
    if request.role != SupportedRole.INVESTIGATOR:
        return
    if not request.customer_id:
        raise HTTPException(status_code=400, detail="Investigator analysis requires a customer_id.")
    if not get_data_service().customer_exists(request.customer_id):
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{request.customer_id}' was not found in real customer data.",
        )


def _format_sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n"
