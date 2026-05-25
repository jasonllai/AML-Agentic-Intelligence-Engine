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


def _as_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


run_store = RunStore()
