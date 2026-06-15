"""AML redesign contract tests for role boundaries and handoff objects."""

from app.agents.router import (
    CANDIDATE_RANKING_AGENT,
    CASE_INVESTIGATION_AGENT,
    FEATURE_CRITIC_AGENT,
    MODEL_EXPLANATION_AGENT,
    TYPOLOGY_MAPPING_AGENT,
    RoleAwareRouter,
)
from app.schemas.analysis import AnalysisRequest
from app.schemas.candidates import (
    DETECTION_CANDIDATE_DISCLAIMER,
    DetectionCandidatePackage,
    InvestigatorFeedback,
)
from app.schemas.roles import SupportedRole


def test_new_primary_tasks_are_supported_by_request_schema() -> None:
    """Role UX should collapse to one strong task per role rather than redundant task labels."""
    data_scientist_request = AnalysisRequest(
        role=SupportedRole.DATA_SCIENTIST,
        task_type="generate_model_driven_candidates",
        query="Generate the top model-driven investigation candidates.",
    )
    investigator_request = AnalysisRequest(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        customer_id="CUST003",
        query="Investigate this model-prioritized candidate.",
    )

    assert data_scientist_request.task_type == "generate_model_driven_candidates"
    assert investigator_request.task_type == "investigate_model_prioritized_candidate"


def test_data_scientist_candidate_route_excludes_case_conclusion_agents() -> None:
    """Data scientists should generate model-prioritized candidates without owning typology conclusions."""
    route = RoleAwareRouter().route(
        role=SupportedRole.DATA_SCIENTIST,
        task_type="generate_model_driven_candidates",
        query="Rank customers for AML investigation.",
    )

    assert CANDIDATE_RANKING_AGENT in route.agents
    assert TYPOLOGY_MAPPING_AGENT not in route.agents
    assert CASE_INVESTIGATION_AGENT not in route.agents


def test_investigator_route_excludes_model_development_agents() -> None:
    """Investigators should review candidates without training, tuning, or feature-engineering ownership."""
    route = RoleAwareRouter().route(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Review the evidence for this model-prioritized customer.",
    )

    assert CASE_INVESTIGATION_AGENT in route.agents
    assert CANDIDATE_RANKING_AGENT not in route.agents
    assert MODEL_EXPLANATION_AGENT not in route.agents
    assert FEATURE_CRITIC_AGENT not in route.agents
    assert TYPOLOGY_MAPPING_AGENT in route.agents


def test_candidate_package_requires_model_prioritization_disclaimer() -> None:
    """Candidate packages must prevent investigators from treating model scores as proof."""
    package = DetectionCandidatePackage(
        candidate_id="cand-001",
        customer_id="CUST003",
        model_run_id="run-001",
        model_version="isolation_forest_v1",
        model_family="isolation_forest",
        rank=1,
        score=0.91,
        score_percentile=0.99,
        threshold=0.75,
        threshold_reason="Top-K alert-volume calibration",
        alert_recommendation="alert",
        top_feature_drivers=[],
        feature_driver_explanations=["amount_sum_total is elevated versus peers"],
        supporting_transaction_slices=[],
        peer_group_baseline={"amount_sum_total": 1000.0},
        model_limitations=["Sparse labels limit supervised performance claims."],
        missing_data=[],
        suggested_investigation_focus=["Review high-value outbound activity."],
    )

    assert package.disclaimer == DETECTION_CANDIDATE_DISCLAIMER
    assert "not proof of suspicious activity" in package.disclaimer


def test_investigator_feedback_captures_case_outcome_for_model_learning() -> None:
    """Investigator disposition should flow back as model-evaluation feedback, not model tuning by investigators."""
    feedback = InvestigatorFeedback(
        case_disposition="monitor",
        typology_assessment="resembles indicators associated with rapid movement of funds",
        false_positive_reason=None,
        useful_model_drivers=["high_value_txn_count"],
        misleading_model_drivers=[],
        missing_features=["known source of funds"],
        investigator_notes="Evidence is insufficient to conclude suspicious activity.",
        label_for_model_evaluation="needs_review",
    )

    assert feedback.case_disposition == "monitor"
    assert feedback.label_for_model_evaluation == "needs_review"

