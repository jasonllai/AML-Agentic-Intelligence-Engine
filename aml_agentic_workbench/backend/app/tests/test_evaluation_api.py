"""Evaluation API tests."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_generate_golden_dataset_endpoint_returns_cases() -> None:
    """Managers and developers should be able to generate golden cases from the API."""
    client = TestClient(create_app())

    response = client.post("/api/v1/evaluations/generate-golden-dataset", json={"case_limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_count"] == 5
    assert payload["cases"][0]["expected_agents"]


def test_run_evaluation_endpoint_executes_analysis_path_for_small_suite() -> None:
    """Evaluation runs should execute the same analysis path used by the application."""
    client = TestClient(create_app())

    response = client.post("/api/v1/evaluations/run", json={"case_limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_count"] == 1
    assert "route_correctness" in payload["metrics"]
    assert payload["cases"][0]["actual_agents"]
