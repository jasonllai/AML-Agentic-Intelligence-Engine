"""SHAP-based Isolation Forest explanation tests."""

from pathlib import Path

import numpy as np
import pandas as pd

from app.guardrails.output_guardrails import OutputGuardrails
from app.ml.feature_dictionary import FEATURE_DEFINITIONS, get_feature_definition
from app.ml.model_service import IsolationForestModelService, ModelService
from app.ml.shap_explanations import build_model_agnostic_shap_drivers
from app.ml.train_model import train_isolation_forest

REAL_DATA_FEATURES = [
    "txn_count_total",
    "amount_sum_total",
    "amount_mean_total",
    "amount_max_total",
    "amount_std_total",
    "debit_amount_sum",
    "credit_amount_sum",
    "debit_credit_amount_ratio",
    "high_value_txn_count",
    "cash_txn_ratio",
    "cross_border_txn_ratio",
    "channel_diversity",
    "active_days_span",
    "days_since_last_txn",
    "channel_count_abm",
    "channel_ratio_abm",
    "channel_count_card",
    "channel_ratio_card",
    "channel_count_cheque",
    "channel_ratio_cheque",
    "channel_count_eft",
    "channel_ratio_eft",
    "channel_count_emt",
    "channel_ratio_emt",
    "channel_count_westernunion",
    "channel_ratio_westernunion",
    "channel_count_wire",
    "channel_ratio_wire",
    "kyc_customer_type_individual",
    "kyc_customer_type_smallbusiness",
    "kyc_income",
    "kyc_sales",
    "kyc_employee_count",
    "kyc_onboard_age_days",
]


def test_feature_dictionary_covers_real_data_feature_schema() -> None:
    """Every real-data feature should have investigator-facing meaning and review guidance."""
    assert set(REAL_DATA_FEATURES) <= set(FEATURE_DEFINITIONS)
    for feature_name in REAL_DATA_FEATURES:
        definition = get_feature_definition(feature_name)
        assert definition.display_name
        assert definition.definition
        assert definition.engineering_formula
        assert definition.investigator_interpretation
        assert definition.suggested_evidence_to_review


def test_model_agnostic_shap_drivers_are_customer_specific_and_ranked_by_contribution() -> None:
    """SHAP driver selection should rank per-customer contributions, not reuse global feature deviations."""
    background = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [2.0, 2.0, 0.0],
            [3.0, 3.0, 0.0],
        ],
        dtype=float,
    )
    candidate = np.array([[2.0, 8.0, 0.0]], dtype=float)

    def score_function(matrix: np.ndarray) -> np.ndarray:
        return matrix[:, 0] * 0.1 + matrix[:, 1] * 2.0

    drivers = build_model_agnostic_shap_drivers(
        score_function=score_function,
        background_matrix=background,
        candidate_matrix=candidate,
        feature_names=["low_weight_feature", "high_weight_feature", "unused_feature"],
        original_values={"low_weight_feature": 2.0, "high_weight_feature": 8.0, "unused_feature": 0.0},
        baselines={"low_weight_feature": 1.5, "high_weight_feature": 1.5, "unused_feature": 0.0},
        z_scores={"low_weight_feature": 0.5, "high_weight_feature": 6.5, "unused_feature": 0.0},
        max_drivers=2,
    )

    assert [driver["feature_name"] for driver in drivers] == ["high_weight_feature", "low_weight_feature"]
    assert drivers[0]["explanation_method"] == "model_agnostic_shap"
    assert drivers[0]["shap_value"] > drivers[1]["shap_value"]
    assert drivers[0]["feature_definition"]
    assert "review" in drivers[0]["suggested_evidence_to_review"].lower()


def test_isolation_forest_candidates_include_rich_shap_driver_details(tmp_path: Path) -> None:
    """Isolation Forest candidate packages should expose SHAP fields and avoid generic driver wording."""
    features = pd.DataFrame(
        [
            {"txn_count_total": 2, "amount_sum_total": 100.0, "channel_count_wire": 0},
            {"txn_count_total": 3, "amount_sum_total": 120.0, "channel_count_wire": 0},
            {"txn_count_total": 4, "amount_sum_total": 160.0, "channel_count_wire": 0},
            {"txn_count_total": 60, "amount_sum_total": 50000.0, "channel_count_wire": 12},
            {"txn_count_total": 5, "amount_sum_total": 180.0, "channel_count_wire": 0},
            {"txn_count_total": 6, "amount_sum_total": 220.0, "channel_count_wire": 1},
        ],
        index=["c1", "c2", "c3", "c-outlier", "c4", "c5"],
    )
    labels = pd.Series([0, 0, 0, 1, 0, 0], index=features.index, name="label")
    train_isolation_forest(features, labels, tmp_path)

    service = ModelService(IsolationForestModelService(tmp_path))
    score = service.score_population(top_k=1)[0]

    assert score["model_family"] == "isolation_forest"
    assert score["top_features"]
    assert score["model_specific_driver_details"]
    driver = score["model_specific_driver_details"][0]
    assert driver["explanation_method"] == "model_agnostic_shap"
    assert "shap_value" in driver
    assert "z_score" in driver
    assert driver["feature_definition"]
    assert driver["engineering_formula"]
    assert driver["investigator_interpretation"]
    assert "contributed to the model prioritization" not in driver["explanation"]


def test_candidate_guardrail_allows_safe_model_explanation_with_typology_boundary() -> None:
    """Candidate explanation guardrails should allow safe review wording while blocking conclusions."""
    guardrails = OutputGuardrails()

    safe = guardrails.evaluate_candidate_explanation(
        "This customer was prioritized for review because wire activity is unusual compared with the modeled "
        "population. Investigators may later map typology indicators only if transaction evidence supports them."
    )
    unsafe = guardrails.evaluate_candidate_explanation(
        "The model proves confirmed suspicious activity and the investigator should file STR."
    )

    assert safe.allowed
    assert not safe.flags
    assert not unsafe.allowed
    assert any(flag.startswith("prohibited_phrase") for flag in unsafe.flags)
