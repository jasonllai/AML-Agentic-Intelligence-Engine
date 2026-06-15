"""Four-model Data Scientist workbench contract tests."""

from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.candidates import DETECTION_CANDIDATE_DISCLAIMER
from app.services.candidate_service import CandidateGenerationService


class FakeDataService:
    """Minimal data service for deterministic model-workbench tests."""

    def get_transactions(self, customer_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        rows = [{"customer_id": customer_id, "transaction_id": "TXN1", "amount": 1000.0, "channel": "wire"}]
        return rows[:limit] if limit is not None else rows

    def get_feature_summary(self, customer_id: str) -> dict[str, Any]:
        return {
            "customer_id": customer_id,
            "amount_sum_total": 1000.0,
            "channel_count_wire": 3.0,
            "kyc_customer_type_individual": 1.0,
        }


class FakeFourModelService:
    """Four-model scorer facade with overlapping top candidates."""

    families = (
        "isolation_forest",
        "autoencoder",
        "variational_autoencoder",
        "conditional_variational_autoencoder",
    )

    def score_all_models(self, top_k: int = 10) -> dict[str, list[dict[str, Any]]]:
        return {family: self._scores(family, top_k=top_k) for family in self.families}

    def score_customer(self, customer_id: str) -> dict[str, Any]:
        return self._scores("isolation_forest", top_k=1)[0] | {"customer_id": customer_id}

    def _scores(self, family: str, *, top_k: int) -> list[dict[str, Any]]:
        return [
            {
                "customer_id": "CUST-001",
                "model_version": f"{family}_v1",
                "model_family": family,
                "risk_score": 0.91,
                "anomaly_score": 0.91,
                "score_percentile": 1.0,
                "rank": 1,
                "alert_recommendation": "alert",
                "top_features": ["amount_sum_total", "channel_count_wire"],
                "model_specific_driver_details": [
                    {
                        "feature_name": "amount_sum_total",
                        "customer_value": 1000.0,
                        "population_baseline": 250.0,
                        "z_score": 2.0,
                        "contribution": 0.4,
                        "reconstruction_contribution": 0.4,
                        "explanation_method": (
                            "shap_kernel" if family == "isolation_forest" else "reconstruction_error"
                        ),
                        "shap_value": 0.4 if family == "isolation_forest" else None,
                        "explanation": f"{family} driver detail",
                    }
                ],
                "explanation_metadata": {"alert_threshold": 0.75, "backend": family},
            },
            {
                "customer_id": f"{family}-002",
                "model_version": f"{family}_v1",
                "model_family": family,
                "risk_score": 0.82,
                "anomaly_score": 0.82,
                "score_percentile": 0.9,
                "rank": 2,
                "alert_recommendation": "alert",
                "top_features": ["channel_count_wire"],
                "model_specific_driver_details": [],
                "explanation_metadata": {"alert_threshold": 0.75, "backend": family},
            },
        ][:top_k]


class UnsafeExplanationClient:
    """LLM client that returns prohibited language for guardrail fallback tests."""

    def generate_structured(self, prompt: str, response_schema: type[Any]) -> Any:
        return response_schema.model_validate(
            {
                "summary": "The model proves suspicious activity.",
                "model_reasoning": "Confirmed suspicious activity.",
                "feature_driver_explanation": "The score proves this customer is suspicious.",
                "suggested_investigator_focus": ["File STR immediately."],
                "limitations": [],
            }
        )

    def generate_text(self, prompt: str) -> str:
        return "unsafe"


def test_candidate_service_returns_four_model_results_and_intersection() -> None:
    """Data Scientist output should include all four model lists plus the top-candidate intersection."""
    service = CandidateGenerationService(
        data_service=FakeDataService(),
        model_service=FakeFourModelService(),
        llm_client=UnsafeExplanationClient(),
    )

    result = service.generate(top_k=2)

    assert set(result["model_results"]) == {
        "isolation_forest",
        "autoencoder",
        "variational_autoencoder",
        "conditional_variational_autoencoder",
        "intersection",
    }
    for family in FakeFourModelService.families:
        assert len(result["model_results"][family]) == 2
        candidate = result["model_results"][family][0]
        assert candidate["disclaimer"] == DETECTION_CANDIDATE_DISCLAIMER
        assert candidate["llm_explanation"]["summary"]
        assert candidate["guardrail_status"] == "fallback_used"
        assert candidate["fallback_explanation"]["summary"]
    assert [candidate["customer_id"] for candidate in result["model_results"]["intersection"]] == ["CUST-001"]
    assert result["model_comparison"][0]["comparison_type"] == "unsupervised_diagnostics"


def test_four_model_scores_are_bounded_and_top_k_limited() -> None:
    """All model outputs should be normalized and limited to the requested candidate count."""
    service = CandidateGenerationService(
        data_service=FakeDataService(),
        model_service=FakeFourModelService(),
    )

    result = service.generate(top_k=1)

    for family in FakeFourModelService.families:
        candidates = result["model_results"][family]
        assert len(candidates) == 1
        assert 0.0 <= candidates[0]["score"] <= 1.0
        assert candidates[0]["alert_recommendation"] == "alert"
    assert all(candidate["model_family"] == "intersection" for candidate in result["model_results"]["intersection"])


def test_deep_model_candidate_drivers_expose_reconstruction_contribution_not_shap() -> None:
    """Deep-model candidate drivers should display reconstruction attribution rather than empty SHAP fields."""
    service = CandidateGenerationService(
        data_service=FakeDataService(),
        model_service=FakeFourModelService(),
    )

    result = service.generate(top_k=1)

    isolation_driver = result["model_results"]["isolation_forest"][0]["top_feature_drivers"][0]
    assert isolation_driver["shap_value"] == 0.4
    assert isolation_driver["population_baseline"] == 250.0

    for family in (
        "autoencoder",
        "variational_autoencoder",
        "conditional_variational_autoencoder",
    ):
        driver = result["model_results"][family][0]["top_feature_drivers"][0]
        assert driver["population_baseline"] == 250.0
        assert driver["z_score"] == 2.0
        assert driver["reconstruction_contribution"] == 0.4
        assert driver["shap_value"] is None


def test_data_scientist_endpoint_omits_judge_cards_and_returns_model_results() -> None:
    """The primary Data Scientist API response should be model-output oriented, not judge-card oriented."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis",
        json={
            "role": "data_scientist",
            "task_type": "generate_model_driven_candidates",
            "query": "Generate model candidates.",
            "require_full_report": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "judge_panel_agent" not in payload["executed_agents"]
    assert payload["judge_scores"] is None
    assert "judge_panel" not in payload["result"]
    assert "model_results" in payload["result"]
    assert "intersection" in payload["result"]["model_results"]
