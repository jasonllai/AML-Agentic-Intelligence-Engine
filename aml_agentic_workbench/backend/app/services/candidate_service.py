"""Services for model-driven candidate ranking and investigator handoff."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.guardrails.output_guardrails import OutputGuardrails
from app.llm.client import LLMClient, get_llm_client
from app.llm.schemas import CandidateExplanationOutput
from app.ml.feature_dictionary import get_feature_definition
from app.ml.model_service import ModelArtifactError, ModelService
from app.schemas.candidates import (
    CandidateExplanation,
    DetectionCandidatePackage,
    FeatureDriver,
    InvestigatorFeedback,
)
from app.services.data_service import DataService


class CandidateGenerationService:
    """Build governed model-prioritized candidate packages."""

    def __init__(
        self,
        data_service: DataService,
        model_service: ModelService | Any | None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.data_service = data_service
        self.model_service = model_service
        self.llm_client = llm_client or get_llm_client()
        self.output_guardrails = OutputGuardrails()

    def generate(self, *, top_k: int = 10, model_run_id: str = "model-run-local") -> dict[str, Any]:
        """Generate ranked candidates for the AML Data Scientist workflow."""
        if self.model_service is None:
            return self._unavailable_result(model_run_id, "No trained model artifact was loaded.")
        try:
            model_scores = self.model_service.score_all_models(top_k=top_k)
        except (ModelArtifactError, AttributeError) as exc:
            return self._unavailable_result(model_run_id, str(exc))

        model_results = {
            family: self._packages_from_scores(scores[:top_k], model_run_id=model_run_id)
            for family, scores in model_scores.items()
        }
        model_results["intersection"] = self._intersection_candidates(model_results)
        candidate_count = sum(len(items) for family, items in model_results.items() if family != "intersection")
        return {
            "model_run_summary": {
                "model_run_id": model_run_id,
                "selected_model_family": "all_supported_models",
                "candidate_count": candidate_count,
                "threshold_method": "per-model unsupervised score normalization and top-K ranking",
                "status": "completed",
            },
            "model_comparison": self._model_comparison_summary(),
            "model_results": model_results,
            "candidate_packages": model_results.get("isolation_forest", []),
            "model_limitations": [
                "Sparse AML labels limit supervised performance claims.",
                "Model scores prioritize review and are not proof of suspicious activity.",
            ],
        }

    def build_case_review(
        self,
        customer_id: str | None,
        *,
        query: str,
        state_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build investigator case review and feedback for one model-prioritized candidate."""
        if not customer_id:
            package = self._empty_candidate_package("missing-customer-id").model_dump(mode="json")
        else:
            package = self.build_candidate_for_customer(customer_id).model_dump(mode="json")

        typology_output = state_outputs.get("typology_mapping_agent", {})
        behaviour_output = state_outputs.get("transaction_behaviour_agent", {})
        disposition = "monitor" if package["alert_recommendation"] in {"alert", "monitor"} else "close"
        feedback = InvestigatorFeedback(
            case_disposition=disposition,
            typology_assessment=(
                typology_output.get("summary")
                or "Evidence is insufficient to conclude suspicious activity; further review may be warranted."
            ),
            false_positive_reason=(
                None
                if disposition != "close"
                else "Model drivers were not supported by case evidence."
            ),
            useful_model_drivers=[
                driver["feature_name"]
                for driver in package.get("top_feature_drivers", [])
            ],
            misleading_model_drivers=[],
            missing_features=list(package.get("missing_data", [])),
            investigator_notes=(
                f"Reviewed model-prioritized candidate for query: {query}. "
                "Model output was treated as prioritization only, not proof."
            ),
            label_for_model_evaluation="needs_review" if disposition != "close" else "false_positive",
        ).model_dump(mode="json")
        return {
            "candidate_package": package,
            "behaviour_review": behaviour_output.get("summary", "No transaction behaviour summary was available."),
            "typology_review": feedback["typology_assessment"],
            "missing_evidence": package.get("missing_data", []),
            "disposition_recommendation": disposition,
            "investigator_feedback": feedback,
        }

    def build_candidate_for_customer(
        self,
        customer_id: str,
        *,
        model_run_id: str = "model-run-local",
    ) -> DetectionCandidatePackage:
        """Build a candidate package for one customer when an investigator opens a case directly."""
        if self.model_service is None:
            return self._empty_candidate_package(customer_id)
        try:
            score = self.model_service.score_customer(customer_id)
        except (ModelArtifactError, ValueError):
            return self._empty_candidate_package(customer_id)
        score.setdefault("rank", 1)
        score.setdefault("score_percentile", float(score.get("risk_score") or 0.0))
        score.setdefault("model_family", score.get("explanation_metadata", {}).get("backend", "isolation_forest"))
        return self._package_from_score(score, model_run_id=model_run_id)

    def _package_from_score(
        self,
        score: dict[str, Any],
        *,
        model_run_id: str,
        include_transactions: bool = True,
    ) -> DetectionCandidatePackage:
        customer_id = str(score["customer_id"])
        features = (
            score.get("explanation_metadata", {}).get("feature_values")
            or self._safe_feature_summary(customer_id)
        )
        threshold = float(score.get("explanation_metadata", {}).get("alert_threshold", 0.0) or 0.0)
        rank = int(score.get("rank", 1))
        details_by_feature = {
            str(detail.get("feature_name")): detail
            for detail in score.get("model_specific_driver_details", [])
            if detail.get("feature_name")
        }
        drivers = [
            self._feature_driver_from_score(
                feature_name,
                features=features,
                detail=details_by_feature.get(feature_name, {}),
            )
            for feature_name in list(score.get("top_features", []))[:5]
        ]
        return DetectionCandidatePackage(
            candidate_id=f"{model_run_id}-{rank:04d}",
            customer_id=customer_id,
            model_run_id=model_run_id,
            model_version=str(score.get("model_version", "untrained")),
            model_family=str(
                score.get("model_family")
                or score.get("explanation_metadata", {}).get("backend", "unknown")
            ),
            rank=rank,
            score=float(score.get("risk_score") or score.get("anomaly_score") or 0.0),
            score_percentile=float(score.get("score_percentile") or 0.0),
            threshold=threshold,
            threshold_reason="Alert threshold from selected model artifact; ranking uses descending risk score.",
            alert_recommendation=str(score.get("alert_recommendation", "model_artifact_required")),
            top_feature_drivers=drivers,
            model_specific_driver_details=list(score.get("model_specific_driver_details", [])),
            feature_driver_explanations=[driver.explanation for driver in drivers],
            **self._guarded_explanation_payload(score, drivers),
            supporting_transaction_slices=self._safe_transactions(customer_id) if include_transactions else [],
            peer_group_baseline={},
            model_limitations=[
                "Model output is prioritization only and is not proof of suspicious activity.",
                "Sparse labels limit supervised performance claims.",
            ],
            missing_data=[] if features else ["customer feature summary"],
            suggested_investigation_focus=[
                f"Review evidence supporting {driver.feature_name}."
                for driver in drivers
            ]
            or ["Review customer transactions and KYC context before disposition."],
        )

    def _packages_from_scores(self, scores: list[dict[str, Any]], *, model_run_id: str) -> list[dict[str, Any]]:
        if not scores:
            return []
        worker_count = min(8, len(scores))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(
                executor.map(
                    lambda score: self._package_from_score(
                        score,
                        model_run_id=model_run_id,
                        include_transactions=False,
                    ).model_dump(mode="json"),
                    scores,
                )
            )

    def _empty_candidate_package(self, customer_id: str) -> DetectionCandidatePackage:
        return DetectionCandidatePackage(
            candidate_id="model-run-local-0000",
            customer_id=customer_id,
            model_run_id="model-run-local",
            model_version="untrained",
            model_family="none",
            rank=1,
            score=0.0,
            score_percentile=0.0,
            threshold=0.0,
            threshold_reason="Model artifact unavailable.",
            alert_recommendation="model_artifact_required",
            model_limitations=["No trained model artifact was available for scoring."],
            missing_data=["model artifact"],
            suggested_investigation_focus=[
                "Resolve model artifact availability before relying on model prioritization."
            ],
        )

    def _safe_transactions(self, customer_id: str) -> list[dict[str, Any]]:
        try:
            return self.data_service.get_transactions(customer_id, limit=5)
        except (AttributeError, ValueError):
            return []

    def _safe_feature_summary(self, customer_id: str) -> dict[str, Any]:
        try:
            return self.data_service.get_feature_summary(customer_id)
        except (AttributeError, ValueError):
            return {}

    @staticmethod
    def _model_comparison_summary() -> list[dict[str, str]]:
        return [
            {
                "model_family": "isolation_forest",
                "status": "scored",
                "comparison_type": "unsupervised_diagnostics",
                "mathematical_objective": "Random isolation path length converted to bounded anomaly score.",
            },
            {
                "model_family": "autoencoder",
                "status": "scored",
                "comparison_type": "unsupervised_diagnostics",
                "mathematical_objective": "Mean squared reconstruction error over standardized features.",
            },
            {
                "model_family": "variational_autoencoder",
                "status": "scored",
                "comparison_type": "unsupervised_diagnostics",
                "mathematical_objective": "Negative ELBO using reconstruction error plus KL divergence.",
            },
            {
                "model_family": "conditional_variational_autoencoder",
                "status": "scored",
                "comparison_type": "unsupervised_diagnostics",
                "mathematical_objective": "Condition-adjusted negative ELBO within explicit peer conditions.",
            },
        ]

    def _guarded_explanation_payload(
        self,
        score: dict[str, Any],
        drivers: list[FeatureDriver],
    ) -> dict[str, Any]:
        fallback = self._fallback_explanation(score, drivers)
        try:
            prompt = self._candidate_explanation_prompt(score, drivers)
            explanation = self.llm_client.generate_structured(prompt, CandidateExplanationOutput)
            explanation_model = CandidateExplanation.model_validate(explanation.model_dump(mode="json"))
            decision = self.output_guardrails.evaluate_candidate_explanation(_explanation_text(explanation_model))
        except Exception as exc:
            fallback_with_error = fallback.model_copy(
                update={"limitations": [*fallback.limitations, f"LLM explanation unavailable: {exc}"]}
            )
            return {
                "llm_explanation": fallback_with_error.model_dump(mode="json"),
                "guardrail_status": "llm_unavailable",
                "guardrail_flags": ["llm_explanation_unavailable"],
                "fallback_explanation": fallback_with_error.model_dump(mode="json"),
            }
        if decision.flags or not decision.allowed:
            return {
                "llm_explanation": fallback.model_dump(mode="json"),
                "guardrail_status": "fallback_used",
                "guardrail_flags": decision.flags,
                "fallback_explanation": fallback.model_dump(mode="json"),
            }
        return {
            "llm_explanation": explanation_model.model_dump(mode="json"),
            "guardrail_status": "passed",
            "guardrail_flags": [],
            "fallback_explanation": fallback.model_dump(mode="json"),
        }

    @staticmethod
    def _candidate_explanation_prompt(score: dict[str, Any], drivers: list[FeatureDriver]) -> str:
        payload = {
            "customer_id": score.get("customer_id"),
            "model_family": score.get("model_family"),
            "rank": score.get("rank"),
            "score": score.get("risk_score") or score.get("anomaly_score"),
            "threshold": score.get("explanation_metadata", {}).get("alert_threshold"),
            "alert_recommendation": score.get("alert_recommendation"),
            "top_feature_drivers": [driver.model_dump(mode="json") for driver in drivers],
            "model_specific_driver_details": score.get("model_specific_driver_details", []),
            "safe_wording_examples": [
                "prioritized for review",
                "model-driven risk signal",
                "unusual compared with the modeled population",
                "investigators should review supporting evidence",
            ],
            "blocked_wording_examples": [
                "confirmed suspicious",
                "model proves suspicious activity",
                "file STR",
                "typology confirmed",
            ],
            "model_limitations": [
                "Model output is prioritization only and is not proof of suspicious activity.",
                "Do not introduce typology, STR, or legal conclusions.",
            ],
        }
        return (
            "Write a concise AML model explanation from only this deterministic model evidence. "
            "Do not add typology conclusions, STR recommendations, legal conclusions, or claims that the model "
            f"proves suspicious activity.\nEvidence: {json.dumps(payload, default=str)}"
        )

    @staticmethod
    def _fallback_explanation(score: dict[str, Any], drivers: list[FeatureDriver]) -> CandidateExplanation:
        family = str(score.get("model_family", "model"))
        driver_summaries = [_driver_summary(driver) for driver in drivers]
        focus = [
            driver.suggested_evidence_to_review
            for driver in drivers
            if driver.suggested_evidence_to_review
        ]
        return CandidateExplanation(
            summary=f"{score.get('customer_id')} was prioritized by {family} for investigator review.",
            model_reasoning=(
                f"The normalized model score was {score.get('risk_score') or score.get('anomaly_score')} "
                f"against threshold {score.get('explanation_metadata', {}).get('alert_threshold')}. "
                "This score is a prioritization signal and does not establish suspicious activity."
            ),
            feature_driver_explanation=(
                " ".join(driver_summaries)
                if driver_summaries
                else "No feature drivers were available for this candidate."
            ),
            suggested_investigator_focus=focus
            or [
                "Review source transactions linked to the model drivers.",
                "Compare activity with expected customer profile before disposition.",
            ],
            limitations=["Model output is not proof of suspicious activity."],
        )

    @staticmethod
    def _feature_driver_from_score(
        feature_name: str,
        *,
        features: dict[str, Any],
        detail: dict[str, Any],
    ) -> FeatureDriver:
        definition = get_feature_definition(feature_name)
        customer_value = detail.get("customer_value", features.get(feature_name))
        baseline = detail.get("population_baseline")
        reconstruction_contribution = detail.get("reconstruction_contribution")
        if reconstruction_contribution is None and _is_reconstruction_method(detail.get("explanation_method")):
            reconstruction_contribution = detail.get("contribution")
        explanation = str(
            detail.get("explanation")
            or (
                f"{definition.display_name} means {definition.definition} Customer value {customer_value} "
                f"compared with population baseline {baseline}. Investigator focus: "
                f"{definition.suggested_evidence_to_review}"
            )
        )
        return FeatureDriver(
            feature_name=feature_name,
            value=customer_value,
            baseline=baseline,
            direction="elevated" if (detail.get("z_score") or 0) >= 0 else "reduced",
            explanation=explanation,
            feature_display_name=str(detail.get("feature_display_name") or definition.display_name),
            feature_definition=str(detail.get("feature_definition") or definition.definition),
            engineering_formula=str(detail.get("engineering_formula") or definition.engineering_formula),
            customer_value=customer_value,
            population_baseline=baseline,
            z_score=detail.get("z_score"),
            shap_value=detail.get("shap_value"),
            shap_direction=detail.get("shap_direction"),
            reconstruction_contribution=reconstruction_contribution,
            investigator_interpretation=str(
                detail.get("investigator_interpretation") or definition.investigator_interpretation
            ),
            suggested_evidence_to_review=str(
                detail.get("suggested_evidence_to_review") or definition.suggested_evidence_to_review
            ),
            explanation_method=detail.get("explanation_method"),
        )

    @staticmethod
    def _intersection_candidates(model_results: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        model_families = [family for family in model_results if family != "intersection"]
        if not model_families:
            return []
        first_family = model_families[0]
        common_ids = {
            model_results[first_family][index]["customer_id"]
            for index in range(len(model_results[first_family]))
        }
        for family in model_families[1:]:
            common_ids &= {candidate["customer_id"] for candidate in model_results[family]}
        scored: list[dict[str, Any]] = []
        for customer_id in common_ids:
            family_candidates = [
                next(candidate for candidate in model_results[family] if candidate["customer_id"] == customer_id)
                for family in model_families
            ]
            representative = dict(family_candidates[0])
            representative["model_family"] = "intersection"
            representative["score"] = round(
                sum(float(candidate["score"]) for candidate in family_candidates) / len(family_candidates),
                6,
            )
            representative["model_specific_driver_details"] = [
                {
                    "model_family": candidate["model_family"],
                    "rank": candidate["rank"],
                    "score": candidate["score"],
                }
                for candidate in family_candidates
            ]
            scored.append(representative)
        scored.sort(key=lambda candidate: (-float(candidate["score"]), str(candidate["customer_id"])))
        for index, candidate in enumerate(scored, start=1):
            candidate["rank"] = index
        return scored

    @staticmethod
    def _unavailable_result(model_run_id: str, reason: str) -> dict[str, Any]:
        return {
            "model_run_summary": {
                "model_run_id": model_run_id,
                "selected_model_family": "none",
                "candidate_count": 0,
                "threshold_method": "unavailable",
                "status": "model_artifact_required",
            },
            "model_comparison": CandidateGenerationService._model_comparison_summary(),
            "model_results": {
                "isolation_forest": [],
                "autoencoder": [],
                "variational_autoencoder": [],
                "conditional_variational_autoencoder": [],
                "intersection": [],
            },
            "candidate_packages": [],
            "model_limitations": [reason],
        }


def _explanation_text(explanation: CandidateExplanation) -> str:
    return " ".join(
        [
            explanation.summary,
            explanation.model_reasoning,
            explanation.feature_driver_explanation,
            *explanation.suggested_investigator_focus,
            *explanation.limitations,
        ]
    )


def _driver_summary(driver: FeatureDriver) -> str:
    display_name = driver.feature_display_name or driver.feature_name
    value_text = (
        f"customer value {driver.customer_value}"
        if driver.customer_value is not None
        else "customer value unavailable"
    )
    baseline_text = (
        f"population baseline {driver.population_baseline}"
        if driver.population_baseline is not None
        else "population baseline unavailable"
    )
    shap_text = (
        f"SHAP value {driver.shap_value} ({driver.shap_direction})"
        if driver.shap_value is not None
        else _reconstruction_summary(driver)
    )
    return (
        f"{display_name}: {driver.feature_definition or driver.feature_name}. "
        f"Engineered as: {driver.engineering_formula or 'formula unavailable'}. "
        f"{value_text} versus {baseline_text}; {shap_text}. "
        f"Investigator focus: {driver.suggested_evidence_to_review or driver.investigator_interpretation}."
    )


def _reconstruction_summary(driver: FeatureDriver) -> str:
    if driver.reconstruction_contribution is not None:
        return (
            f"reconstruction contribution {driver.reconstruction_contribution} "
            f"({driver.explanation_method or 'reconstruction_error'})"
        )
    return f"explanation method {driver.explanation_method or 'feature dictionary'}"


def _is_reconstruction_method(value: object) -> bool:
    return str(value) in {
        "reconstruction_error",
        "vae_reconstruction_error",
        "conditional_vae_reconstruction_error",
    }
