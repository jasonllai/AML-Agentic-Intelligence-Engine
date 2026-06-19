"""In-memory run store for local workbench report/history endpoints."""

from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.schemas.analysis import AnalysisResponse
from app.schemas.reports import ReportDetailResponse, ReportSummary


class RunStore:
    """Thread-safe in-memory run store.

    This is intentionally small and replaceable. PostgreSQL-backed persistence
    can take over behind the same report schemas.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, ReportDetailResponse] = {}

    def add(self, response: AnalysisResponse, task_type: str) -> ReportDetailResponse:
        """Store an analysis response as a report detail record."""
        result = response.result
        detail = ReportDetailResponse(
            run_id=response.run_id,
            role=response.role,
            task_type=task_type,
            status=response.status,
            guardrail_status=response.guardrail_status,
            final_report=_as_str(result.get("final_report")),
            model_run_summary=_as_optional_dict(result.get("model_run_summary")),
            candidate_packages=_as_list(result.get("candidate_packages")),
            investigation_case_review=_as_optional_dict(result.get("investigation_case_review")),
            planner_decisions=_as_list(result.get("planner_decisions")),
            critic_reviews=_as_list(result.get("critic_reviews")),
            stop_reason=_as_str(result.get("stop_reason")),
            refinement_rounds=_as_int(result.get("refinement_rounds")),
            guardrail_remediation_rounds=_as_int(result.get("guardrail_remediation_rounds")),
            guardrail_remediations=_as_list(result.get("guardrail_remediations")),
            governance_status=_as_str(result.get("governance_status")),
            judge_status=_as_str(result.get("judge_status")),
            judge_failure_reasons=_as_list(result.get("judge_failure_reasons")),
            executed_agents=response.executed_agents,
            judge_scores=response.judge_scores,
            route_explanation=response.route_explanation,
            agent_outputs=_as_dict(result.get("agent_outputs")),
            audit_trace=_as_list(result.get("audit_trace")),
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._runs[response.run_id] = detail
        return detail

    def get(self, run_id: str) -> ReportDetailResponse | None:
        """Return a report detail by run identifier."""
        with self._lock:
            return self._runs.get(run_id)

    def list(self) -> list[ReportSummary]:
        """Return run history summaries newest first."""
        with self._lock:
            reports = list(self._runs.values())
        reports.sort(key=lambda report: report.created_at, reverse=True)
        return [
            ReportSummary(
                run_id=report.run_id,
                title=f"{report.role.value} - {report.task_type}",
                role=report.role,
                task_type=report.task_type,
                status=report.status,
                overall_judge_score=(report.judge_scores or {}).get("overall_score"),
                guardrail_status=report.guardrail_status,
                created_at=report.created_at,
            )
            for report in reports
        ]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_optional_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


run_store = RunStore()
