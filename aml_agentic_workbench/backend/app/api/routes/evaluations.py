"""System evaluation endpoints."""

from fastapi import APIRouter, HTTPException

from app.api.routes.analysis import create_analysis
from app.evaluation.golden_dataset import build_golden_dataset
from app.evaluation.runner import run_evaluation
from app.schemas.analysis import AnalysisRequest
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunSummary,
    GoldenCase,
    GoldenDatasetRequest,
    GoldenDatasetResponse,
)
from app.services.evaluation_store import evaluation_store

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/generate-golden-dataset", response_model=GoldenDatasetResponse)
async def generate_golden_dataset(request: GoldenDatasetRequest) -> GoldenDatasetResponse:
    """Generate and store a deterministic golden dataset for system evaluation."""
    cases = build_golden_dataset(case_limit=request.case_limit)
    evaluation_store.set_golden_cases(cases)
    return GoldenDatasetResponse(case_count=len(cases), cases=cases)


@router.post("/run", response_model=EvaluationRunSummary)
async def run_system_evaluation(request: EvaluationRunRequest) -> EvaluationRunSummary:
    """Run the active or newly generated golden dataset through the analysis path."""
    cases = evaluation_store.golden_cases or build_golden_dataset(case_limit=request.case_limit)
    selected_cases = cases[: request.case_limit]
    run = await run_evaluation(selected_cases, _execute_analysis_case)
    evaluation_store.add_run(run)
    return run


@router.get("", response_model=list[EvaluationRunSummary])
async def list_evaluations() -> list[EvaluationRunSummary]:
    """List recent evaluation runs."""
    return evaluation_store.list_runs()


@router.get("/{run_id}", response_model=EvaluationRunSummary)
async def get_evaluation(run_id: str) -> EvaluationRunSummary:
    """Return a single evaluation run by ID."""
    run = evaluation_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    return run


async def _execute_analysis_case(case: GoldenCase):
    return await create_analysis(
        AnalysisRequest(
            role=case.role,
            task_type=case.task_type,
            customer_id=case.customer_id,
            query=case.query,
            require_full_report=True,
        )
    )
