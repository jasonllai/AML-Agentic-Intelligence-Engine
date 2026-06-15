"""Candidate ranking and investigator handoff workflow tests."""

from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.testclient import TestClient

from app.main import create_app
from app.ml.model_service import IsolationForestModelService, ModelService
from app.ml.train_model import train_isolation_forest
from app.schemas.analysis import AnalysisResponse
from app.schemas.candidates import DETECTION_CANDIDATE_DISCLAIMER
from app.schemas.roles import SupportedRole
from app.services.candidate_service import CandidateGenerationService
from app.services.run_store import RunStore


class FakeDataService:
    """Small data facade for deterministic candidate package tests."""

    def get_transactions(self, customer_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        rows = [
            {"customer_id": customer_id, "transaction_id": "TXN1", "amount": 12500.0, "channel": "wire"},
            {"customer_id": customer_id, "transaction_id": "TXN2", "amount": 300.0, "channel": "card"},
        ]
        return rows[:limit] if limit is not None else rows

    def get_feature_summary(self, customer_id: str) -> dict[str, Any]:
        return {
            "customer_id": customer_id,
            "amount_sum_total": 12800.0,
            "txn_count_total": 2,
            "top_features": ["amount_sum_total"],
        }


class FakeModelService:
    """Deterministic scorer for candidate package tests."""

    def score_all_models(self, top_k: int = 10) -> dict[str, list[dict[str, Any]]]:
        scores = self.score_population(top_k=top_k)
        return {
            "isolation_forest": scores,
            "autoencoder": scores,
            "variational_autoencoder": scores,
            "conditional_variational_autoencoder": scores,
        }

    def score_population(self, top_k: int = 10) -> list[dict[str, Any]]:
        scores = [
            {
                "customer_id": "CUST-HIGH",
                "model_version": "isolation_forest_v1",
                "model_family": "isolation_forest",
                "risk_score": 0.92,
                "anomaly_score": 0.92,
                "score_percentile": 1.0,
                "rank": 1,
                "alert_recommendation": "alert",
                "top_features": ["amount_sum_total"],
                "explanation_metadata": {"alert_threshold": 0.75},
            },
            {
                "customer_id": "CUST-LOW",
                "model_version": "isolation_forest_v1",
                "model_family": "isolation_forest",
                "risk_score": 0.24,
                "anomaly_score": 0.24,
                "score_percentile": 0.5,
                "rank": 2,
                "alert_recommendation": "no_alert",
                "top_features": ["txn_count_total"],
                "explanation_metadata": {"alert_threshold": 0.75},
            },
        ]
        return scores[:top_k]


def test_model_service_scores_population_with_ranked_candidates(tmp_path: Path) -> None:
    """Data science workflow needs population-level ranking, not only single-customer scoring."""
    features = pd.DataFrame(
        [
            {"txn_count_total": 2, "amount_sum_total": 100.0, "channel_diversity": 1},
            {"txn_count_total": 45, "amount_sum_total": 25000.0, "channel_diversity": 5},
            {"txn_count_total": 4, "amount_sum_total": 400.0, "channel_diversity": 1},
        ],
        index=["c1", "c2", "c3"],
    )
    labels = pd.Series([0, 1, 0], index=features.index, name="label")
    train_isolation_forest(features, labels, tmp_path)
    service = ModelService(IsolationForestModelService(tmp_path))

    scores = service.score_population(top_k=2)

    assert len(scores) == 2
    assert scores[0]["rank"] == 1
    assert scores[0]["risk_score"] >= scores[1]["risk_score"]
    assert 0.0 <= scores[0]["score_percentile"] <= 1.0


def test_deep_model_service_driver_details_include_baseline_and_reconstruction_contribution(tmp_path: Path) -> None:
    """AE/VAE/CVAE driver details should expose population baseline and reconstruction attribution."""
    features = pd.DataFrame(
        [
            {"txn_count_total": 2, "amount_sum_total": 100.0, "channel_diversity": 1},
            {"txn_count_total": 45, "amount_sum_total": 25000.0, "channel_diversity": 5},
            {"txn_count_total": 4, "amount_sum_total": 400.0, "channel_diversity": 1},
            {"txn_count_total": 12, "amount_sum_total": 2000.0, "channel_diversity": 2},
        ],
        index=["c1", "c2", "c3", "c4"],
    )
    labels = pd.Series([0, 1, 0, 0], index=features.index, name="label")
    train_isolation_forest(features, labels, tmp_path)
    service = ModelService(IsolationForestModelService(tmp_path))

    scores = service.score_all_models(top_k=1)

    expected_methods = {
        "autoencoder": "reconstruction_error",
        "variational_autoencoder": "vae_reconstruction_error",
        "conditional_variational_autoencoder": "conditional_vae_reconstruction_error",
    }
    for family, expected_method in expected_methods.items():
        detail = scores[family][0]["model_specific_driver_details"][0]
        assert detail["population_baseline"] is not None
        assert detail["customer_value"] is not None
        assert detail["z_score"] is not None
        assert detail["reconstruction_contribution"] >= 0.0
        assert detail["explanation_method"] == expected_method
        assert detail.get("shap_value") is None


def test_candidate_service_builds_investigator_ready_packages() -> None:
    """Data scientist output should be a governed package investigators can consume."""
    service = CandidateGenerationService(data_service=FakeDataService(), model_service=FakeModelService())

    result = service.generate(top_k=1)

    assert result["model_run_summary"]["candidate_count"] == 4
    package = result["model_results"]["isolation_forest"][0]
    assert package["customer_id"] == "CUST-HIGH"
    assert package["rank"] == 1
    assert package["disclaimer"] == DETECTION_CANDIDATE_DISCLAIMER
    assert package["supporting_transaction_slices"] == []
    assert package["llm_explanation"]["summary"]
    assert package["top_feature_drivers"][0]["feature_name"] == "amount_sum_total"


def test_data_scientist_endpoint_returns_ranked_candidate_packages() -> None:
    """The primary Data Scientist task should return ranked candidate packages through the API."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "data_scientist",
            "task_type": "generate_model_driven_candidates",
            "query": "Generate top model-driven AML investigation candidates.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    packages = payload["result"]["candidate_packages"]
    assert payload["executed_agents"][0] == "candidate_ranking_agent"
    assert packages
    assert packages[0]["disclaimer"] == DETECTION_CANDIDATE_DISCLAIMER


def test_investigator_endpoint_returns_case_feedback_for_model_learning() -> None:
    """The primary Investigator task should produce case feedback rather than model-development output."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "investigator",
            "task_type": "investigate_model_prioritized_candidate",
            "customer_id": "CUST003",
            "query": "Investigate this model-prioritized candidate and return feedback.",
            "selected_agents": ["case_investigation_agent"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    case_review = payload["result"]["investigation_case_review"]
    assert case_review["candidate_package"]["disclaimer"] == DETECTION_CANDIDATE_DISCLAIMER
    assert case_review["investigator_feedback"]["case_disposition"] in {
        "close",
        "monitor",
        "escalate",
        "prepare_reportable_suspicion",
    }


def test_investigator_primary_route_uses_local_typology_fallback_without_pgvector() -> None:
    """The primary investigator handoff should stay reviewable even when pgvector is not running locally."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "investigator",
            "task_type": "investigate_model_prioritized_candidate",
            "customer_id": "CUST003",
            "query": "Investigate this model-prioritized candidate and return typology feedback.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "typology_mapping_agent" in payload["executed_agents"]
    typology_output = payload["result"]["agent_outputs"]["typology_mapping_agent"]
    assert any("local keyword fallback" in item for item in typology_output["limitations"])


def test_run_store_preserves_candidate_packages_for_report_history() -> None:
    """Saved reports should retain the handoff fields needed by frontend history views."""
    store = RunStore()
    response = AnalysisResponse(
        run_id="run-candidates",
        role=SupportedRole.DATA_SCIENTIST,
        executed_agents=["candidate_ranking_agent", "guardrail_agent"],
        status="completed",
        guardrail_status="passed",
        result={
            "final_report": "Model-driven candidate handoff.",
            "agent_outputs": {},
            "audit_trace": [],
            "candidate_packages": [{"candidate_id": "cand-1", "customer_id": "CUST003"}],
            "model_run_summary": {"candidate_count": 1},
            "investigation_case_review": {"disposition_recommendation": "monitor"},
        },
    )

    detail = store.add(response, task_type="generate_model_driven_candidates")

    assert detail.candidate_packages == [{"candidate_id": "cand-1", "customer_id": "CUST003"}]
    assert detail.model_run_summary == {"candidate_count": 1}
    assert detail.investigation_case_review == {"disposition_recommendation": "monitor"}
