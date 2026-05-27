"""In-memory evaluation run store for API/dashboard v1."""

from app.schemas.evaluation import EvaluationRunSummary, GoldenCase


class EvaluationStore:
    """Store generated golden cases and recent evaluation runs in process memory."""

    def __init__(self) -> None:
        self.golden_cases: list[GoldenCase] = []
        self.runs: dict[str, EvaluationRunSummary] = {}

    def set_golden_cases(self, cases: list[GoldenCase]) -> None:
        """Replace the active generated golden dataset."""
        self.golden_cases = cases

    def add_run(self, run: EvaluationRunSummary) -> None:
        """Persist an evaluation run summary."""
        self.runs[run.run_id] = run

    def list_runs(self) -> list[EvaluationRunSummary]:
        """Return recent runs newest first."""
        return sorted(self.runs.values(), key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> EvaluationRunSummary | None:
        """Return one run by ID."""
        return self.runs.get(run_id)


evaluation_store = EvaluationStore()
