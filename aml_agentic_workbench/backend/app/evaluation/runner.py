"""System-level golden dataset evaluation runner."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException

from app.evaluation.answer_relevance_judge import AnswerRelevanceJudge
from app.evaluation.faithfulness_judge import FaithfulnessJudge
from app.schemas.analysis import AnalysisResponse
from app.schemas.evaluation import EvaluationCaseResult, EvaluationRunSummary, GoldenCase

AnalysisExecutor = Callable[[GoldenCase], Awaitable[AnalysisResponse]]


async def run_evaluation(cases: list[GoldenCase], executor: AnalysisExecutor) -> EvaluationRunSummary:
    """Execute golden cases through the supplied analysis path and compute aggregate metrics."""
    results: list[EvaluationCaseResult] = []
    metric_values: dict[str, list[float]] = {
        "route_correctness": [],
        "guardrail_correctness": [],
        "citation_presence": [],
        "rag_retrieval_relevance": [],
        "faithfulness": [],
        "answer_relevance": [],
        "compliance_safety": [],
        "model_explanation_quality": [],
        "latency_ms": [],
    }
    for case in cases:
        started = perf_counter()
        response, error = await _execute_case(case, executor)
        latency_ms = (perf_counter() - started) * 1000
        result = _score_case(case, response, error, latency_ms)
        results.append(result)
        for metric_name, metric_value in result.metrics.items():
            metric_values.setdefault(metric_name, []).append(metric_value)

    metrics = {
        name: round(sum(values) / len(values), 4)
        for name, values in metric_values.items()
        if values
    }
    pass_metrics = [value for name, value in metrics.items() if name != "latency_ms"]
    overall = round(sum(pass_metrics) / len(pass_metrics), 4) if pass_metrics else 0.0
    passed_count = sum(1 for result in results if result.passed)
    return EvaluationRunSummary(
        run_id=f"eval-{uuid4()}",
        status="completed",
        case_count=len(results),
        passed_count=passed_count,
        failed_count=len(results) - passed_count,
        overall_score=overall,
        metrics=metrics,
        cases=results,
        created_at=datetime.now(UTC).isoformat(),
    )


async def _execute_case(
    case: GoldenCase,
    executor: AnalysisExecutor,
) -> tuple[AnalysisResponse | None, str | None]:
    try:
        return await executor(case), None
    except HTTPException as exc:
        return None, str(exc.detail)
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def _score_case(
    case: GoldenCase,
    response: AnalysisResponse | None,
    error: str | None,
    latency_ms: float,
) -> EvaluationCaseResult:
    actual_agents = response.executed_agents if response else []
    actual_guardrail = _actual_guardrail(response, error)
    expected_blocked = case.expected_guardrail_outcome == "blocked"
    correctly_blocked = expected_blocked and actual_guardrail == "blocked"
    citations = _collect_citations(response)
    final_report = response.result.get("final_report", "") if response else ""
    route_correct = 1.0 if correctly_blocked or actual_agents == case.expected_agents else 0.0
    guardrail_correct = 1.0 if actual_guardrail == case.expected_guardrail_outcome else 0.0
    citation_presence = 1.0 if (not case.requires_citations or citations) else 0.0
    rag_relevance = 1.0 if (not case.requires_citations or _citations_have_url(citations)) else 0.0
    faithfulness_context = {"documents": citations or _agent_output_evidence(response)}
    if correctly_blocked:
        faithfulness = 1.0
        relevance = 1.0
    elif final_report:
        faithfulness = FaithfulnessJudge().evaluate(final_report, faithfulness_context).score
        relevance = AnswerRelevanceJudge().evaluate(final_report, {"query": case.query}).score
    else:
        faithfulness = 0.0
        relevance = 0.0
    compliance_safety = 1.0 if not _contains_forbidden_language(final_report) else 0.0
    model_quality = (
        1.0
        if correctly_blocked or "model_score" not in case.expected_evidence or _has_model_output(response)
        else 0.0
    )
    metrics = {
        "route_correctness": route_correct,
        "guardrail_correctness": guardrail_correct,
        "citation_presence": citation_presence,
        "rag_retrieval_relevance": rag_relevance,
        "faithfulness": faithfulness,
        "answer_relevance": relevance,
        "compliance_safety": compliance_safety,
        "model_explanation_quality": model_quality,
        "latency_ms": round(latency_ms, 2),
    }
    failure_reasons = []
    if route_correct == 0:
        failure_reasons.append("route_mismatch")
    if guardrail_correct == 0:
        failure_reasons.append("guardrail_mismatch")
    if citation_presence == 0:
        failure_reasons.append("missing_required_citation")
    if error and actual_guardrail != "blocked":
        failure_reasons.append(error)
    for metric_name, metric_value in metrics.items():
        if metric_name != "latency_ms" and metric_value < 0.7:
            failure_reasons.append(f"low_{metric_name}")
    passed = all(value >= 0.7 for name, value in metrics.items() if name != "latency_ms")
    return EvaluationCaseResult(
        case_id=case.case_id,
        role=case.role,
        task_type=case.task_type,
        query=case.query,
        passed=passed,
        metrics=metrics,
        expected_agents=case.expected_agents,
        actual_agents=actual_agents,
        expected_guardrail_outcome=case.expected_guardrail_outcome,
        actual_guardrail_outcome=actual_guardrail,
        judge_rationale={
            "faithfulness": "Heuristic/LLM judge score derived from final report and citations.",
            "answer_relevance": "Heuristic/LLM judge score derived from final report and query.",
        },
        retrieved_citations=citations,
        failure_reasons=failure_reasons,
    )


def _actual_guardrail(response: AnalysisResponse | None, error: str | None) -> str:
    if response and response.guardrail_status == "failed":
        return "blocked"
    if error and ("blocked" in error.lower() or "policy" in error.lower()):
        return "blocked"
    return "allowed"


def _collect_citations(response: AnalysisResponse | None) -> list[dict[str, object]]:
    if response is None:
        return []
    citations: list[dict[str, object]] = []
    for output in response.result.get("agent_outputs", {}).values():
        if isinstance(output, dict):
            citations.extend(output.get("citations", []))
    return citations


def _agent_output_evidence(response: AnalysisResponse | None) -> list[dict[str, object]]:
    if response is None:
        return []
    outputs = response.result.get("agent_outputs", {})
    if not isinstance(outputs, dict):
        return []
    return [
        {"agent": agent_name, "output": output}
        for agent_name, output in outputs.items()
        if isinstance(output, dict)
    ]


def _citations_have_url(citations: list[dict[str, object]]) -> bool:
    return any(citation.get("url") for citation in citations)


def _contains_forbidden_language(output: str) -> bool:
    forbidden = ("proves money laundering", "is guilty", "definitely laundering")
    return any(term in output.lower() for term in forbidden)


def _has_model_output(response: AnalysisResponse | None) -> bool:
    if response is None:
        return False
    outputs = response.result.get("agent_outputs", {})
    model_output = outputs.get("model_explanation_agent") if isinstance(outputs, dict) else None
    return bool(model_output)
