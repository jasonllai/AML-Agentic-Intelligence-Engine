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


def test_analysis_endpoint_allows_browser_preflight() -> None:
    """Browser clients need CORS preflight to succeed before submitting analysis."""
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/analysis",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code in {200, 204}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_local_frontend_ports_allow_preflight_for_analysis_and_evaluations() -> None:
    """Next.js may choose another local port, so local development CORS should stay usable."""
    client = TestClient(create_app())

    analysis_response = client.options(
        "/api/v1/analysis",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    evaluations_response = client.options(
        "/api/v1/evaluations",
        headers={
            "Origin": "http://127.0.0.1:3002",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    run_response = client.options(
        "/api/v1/evaluations/run",
        headers={
            "Origin": "http://localhost:3003",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert analysis_response.status_code in {200, 204}
    assert evaluations_response.status_code in {200, 204}
    assert run_response.status_code in {200, 204}
    assert analysis_response.headers["access-control-allow-origin"] == "http://localhost:3001"
    assert evaluations_response.headers["access-control-allow-origin"] == "http://127.0.0.1:3002"
    assert run_response.headers["access-control-allow-origin"] == "http://localhost:3003"


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
            "selected_agents": ["transaction_behaviour_agent"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed_agents"] == [
        "transaction_behaviour_agent",
        "guardrail_agent",
    ]
    assert payload["guardrail_status"] == "passed"
    assert payload["route_explanation"] is not None
    assert "final_report" in payload["result"]


def test_analysis_endpoint_returns_service_unavailable_when_pgvector_is_missing() -> None:
    """Typology routes should fail with an operator action, not an unhandled 500."""
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "investigator",
            "task_type": "investigator_summary",
            "customer_id": "CUST003",
            "query": "Map velocity spike to typology indicators.",
            "selected_agents": ["typology_mapping_agent"],
        },
    )

    assert response.status_code == 503
    assert "ingest_pgvector" in response.json()["detail"]


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
