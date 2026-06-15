"""Model-agnostic SHAP utilities for AML anomaly-score explanations."""

import logging
from collections.abc import Callable
from typing import Any

import numpy as np

from app.ml.feature_dictionary import get_feature_definition

logging.getLogger("shap").setLevel(logging.WARNING)

ScoreFunction = Callable[[np.ndarray], np.ndarray]


class ModelAgnosticShapExplainer:
    """Small wrapper around SHAP KernelExplainer for scalar anomaly-score functions."""

    def __init__(
        self,
        *,
        score_function: ScoreFunction,
        background_matrix: np.ndarray,
        feature_names: list[str],
        nsamples: int | None = None,
    ) -> None:
        import shap

        if background_matrix.ndim != 2:
            raise ValueError("SHAP background matrix must be two-dimensional.")
        if background_matrix.shape[1] != len(feature_names):
            raise ValueError("SHAP background feature dimension must match feature names.")
        self.score_function = score_function
        self.feature_names = feature_names
        self.nsamples = nsamples or min(2 * len(feature_names) + 64, 256)
        self._explainer = shap.KernelExplainer(self._predict, background_matrix)

    def explain(
        self,
        *,
        candidate_matrix: np.ndarray,
        original_values: dict[str, Any],
        baselines: dict[str, float],
        z_scores: dict[str, float],
        max_drivers: int = 5,
    ) -> list[dict[str, Any]]:
        """Return top SHAP-ranked feature-driver dictionaries for one candidate."""
        if candidate_matrix.shape != (1, len(self.feature_names)):
            raise ValueError("SHAP candidate matrix must contain one row with the model feature dimension.")
        raw_values = self._explainer.shap_values(candidate_matrix, nsamples=self.nsamples, silent=True)
        values = _coerce_single_output_values(raw_values, len(self.feature_names))
        ranked_indexes = np.argsort(np.abs(values))[::-1][:max_drivers]
        drivers: list[dict[str, Any]] = []
        for index in ranked_indexes:
            feature_name = self.feature_names[int(index)]
            shap_value = float(values[int(index)])
            if shap_value == 0.0:
                continue
            definition = get_feature_definition(feature_name)
            direction = "increased_score" if shap_value > 0 else "decreased_score"
            customer_value = original_values.get(feature_name)
            baseline = baselines.get(feature_name)
            z_score = z_scores.get(feature_name)
            drivers.append(
                {
                    "feature_name": feature_name,
                    "feature_display_name": definition.display_name,
                    "feature_definition": definition.definition,
                    "engineering_formula": definition.engineering_formula,
                    "customer_value": _round_optional(customer_value),
                    "population_baseline": _round_optional(baseline),
                    "z_score": _round_optional(z_score),
                    "shap_value": round(shap_value, 6),
                    "shap_direction": direction,
                    "contribution": round(abs(shap_value), 6),
                    "investigator_interpretation": definition.investigator_interpretation,
                    "suggested_evidence_to_review": definition.suggested_evidence_to_review,
                    "explanation_method": "model_agnostic_shap",
                    "explanation": _driver_explanation(
                        feature_name=feature_name,
                        definition=definition.definition,
                        customer_value=customer_value,
                        baseline=baseline,
                        z_score=z_score,
                        shap_value=shap_value,
                        direction=direction,
                        evidence=definition.suggested_evidence_to_review,
                    ),
                }
            )
        return drivers

    def _predict(self, matrix: np.ndarray) -> np.ndarray:
        scores = np.asarray(self.score_function(np.asarray(matrix, dtype=float)), dtype=float)
        return scores.reshape(-1)


def build_model_agnostic_shap_drivers(
    *,
    score_function: ScoreFunction,
    background_matrix: np.ndarray,
    candidate_matrix: np.ndarray,
    feature_names: list[str],
    original_values: dict[str, Any],
    baselines: dict[str, float],
    z_scores: dict[str, float],
    max_drivers: int = 5,
    nsamples: int | None = None,
) -> list[dict[str, Any]]:
    """Build SHAP driver dictionaries with feature-dictionary context."""
    explainer = ModelAgnosticShapExplainer(
        score_function=score_function,
        background_matrix=background_matrix,
        feature_names=feature_names,
        nsamples=nsamples,
    )
    return explainer.explain(
        candidate_matrix=candidate_matrix,
        original_values=original_values,
        baselines=baselines,
        z_scores=z_scores,
        max_drivers=max_drivers,
    )


def _coerce_single_output_values(raw_values: Any, feature_count: int) -> np.ndarray:
    if isinstance(raw_values, list):
        raw_values = raw_values[0]
    values = np.asarray(raw_values, dtype=float)
    if values.ndim == 3:
        values = values[:, :, 0]
    if values.ndim == 2:
        values = values[0]
    values = values.reshape(-1)
    if len(values) != feature_count:
        raise ValueError("SHAP values feature dimension did not match feature names.")
    return values


def _driver_explanation(
    *,
    feature_name: str,
    definition: str,
    customer_value: Any,
    baseline: Any,
    z_score: Any,
    shap_value: float,
    direction: str,
    evidence: str,
) -> str:
    direction_text = "pushed the Isolation Forest score higher" if direction == "increased_score" else (
        "pushed the Isolation Forest score lower"
    )
    return (
        f"{feature_name} means {definition} Customer value {customer_value} compared with population baseline "
        f"{baseline} (z-score {_round_optional(z_score)}). Its SHAP value {_round_optional(shap_value)} "
        f"{direction_text}. Investigator focus: {evidence}"
    )


def _round_optional(value: Any) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return value
