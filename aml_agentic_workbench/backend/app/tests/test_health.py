"""Health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    """Health endpoint should return service liveness metadata."""
    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "AML Agentic Intelligence Workbench"


def test_analysis_endpoint_executes_dynamic_route() -> None:
    """Analysis endpoint should execute the selected route and return route explanation."""
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "investigator",
            "task_type": "investigator_summary",
            "customer_id": "CUST003",
            "query": "Summarize velocity spike and new counterparty burst.",
            "selected_agents": ["transaction_behaviour_agent", "typology_mapping_agent"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed_agents"] == [
        "transaction_behaviour_agent",
        "typology_mapping_agent",
        "guardrail_agent",
    ]
    assert payload["guardrail_status"] == "passed"
    assert payload["route_explanation"] is not None
    assert "final_report" in payload["result"]


def test_analysis_endpoint_blocks_unauthorized_selected_agent() -> None:
    """Analysis endpoint should reject selected agents outside role permissions."""
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "compliance_strategy",
            "task_type": "compliance_typology_review",
            "query": "Map compliance typology.",
            "selected_agents": ["transaction_behaviour_agent"],
        },
    )

    assert response.status_code == 403
