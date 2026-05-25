"""LLM-backed agent schema tests using the mock client."""

from app.agents.nodes import make_agent_nodes
from app.agents.router import (
    EVIDENCE_ASSEMBLY_AGENT,
    FEATURE_CRITIC_AGENT,
    GUARDRAIL_AGENT,
    MODEL_EXPLANATION_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import initial_state
from app.llm.mock_client import MockLLMClient
from app.llm.schemas import (
    EvidenceAssemblyOutput,
    FeatureCriticOutput,
    ModelExplanationOutput,
    TransactionBehaviourOutput,
    TypologyMappingOutput,
)
from app.schemas.roles import SupportedRole


def test_transaction_behaviour_agent_returns_valid_schema() -> None:
    """Transaction behaviour agent should emit the required structured schema."""
    nodes = make_agent_nodes(llm_client=MockLLMClient())
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Review velocity and counterparties.",
        customer_id="CUST003",
    )

    final_state = nodes[TRANSACTION_BEHAVIOUR_AGENT](state)
    structured = final_state["agent_outputs"][TRANSACTION_BEHAVIOUR_AGENT]["structured_output"]

    output = TransactionBehaviourOutput.model_validate(structured)
    assert output.behavioural_summary
    assert "velocity_change" in output.key_features


def test_model_agent_includes_uncertainty_language() -> None:
    """Model explanation should clearly avoid proof language."""
    nodes = make_agent_nodes(llm_client=MockLLMClient())
    state = initial_state(
        role=SupportedRole.MODEL_VALIDATOR,
        task_type="model_validation_review",
        query="Explain model score uncertainty.",
        customer_id="CUST007",
    )

    final_state = nodes[MODEL_EXPLANATION_AGENT](state)
    structured = final_state["agent_outputs"][MODEL_EXPLANATION_AGENT]["structured_output"]

    output = ModelExplanationOutput.model_validate(structured)
    combined = " ".join([output.score_interpretation, output.model_uncertainty, *output.caveats]).lower()
    assert "not proof" in combined


def test_typology_agent_requires_citations_and_careful_language() -> None:
    """Typology mapping should include citations and non-conclusive language."""
    nodes = make_agent_nodes(llm_client=MockLLMClient())
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Map velocity spike to typology indicators.",
        customer_id="CUST003",
    )
    state = nodes[TRANSACTION_BEHAVIOUR_AGENT](state)

    final_state = nodes[TYPOLOGY_MAPPING_AGENT](state)
    structured = final_state["agent_outputs"][TYPOLOGY_MAPPING_AGENT]["structured_output"]

    output = TypologyMappingOutput.model_validate(structured)
    assert output.citations
    assert "evidence is insufficient to conclude" in output.careful_language_summary


def test_feature_critic_returns_valid_feature_suggestions() -> None:
    """Feature critic should return complete PySpark feature recommendations."""
    nodes = make_agent_nodes(llm_client=MockLLMClient())
    state = initial_state(
        role=SupportedRole.DATA_SCIENTIST,
        task_type="feature_quality_review",
        query="Critique features and suggest PySpark features.",
        customer_id="CUST006",
    )

    final_state = nodes[FEATURE_CRITIC_AGENT](state)
    structured = final_state["agent_outputs"][FEATURE_CRITIC_AGENT]["structured_output"]

    output = FeatureCriticOutput.model_validate(structured)
    suggestion = output.recommended_pyspark_features[0]
    assert suggestion.feature_name
    assert suggestion.required_columns
    assert "groupBy" in suggestion.pyspark_pseudocode


def test_evidence_assembly_adapts_to_partial_agent_route() -> None:
    """Evidence assembly should omit sections for agents that were not executed."""
    nodes = make_agent_nodes(llm_client=MockLLMClient())
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigator_summary",
        query="Summarize behaviour only.",
        customer_id="CUST003",
        route=[TRANSACTION_BEHAVIOUR_AGENT, EVIDENCE_ASSEMBLY_AGENT, GUARDRAIL_AGENT],
    )
    state = nodes[TRANSACTION_BEHAVIOUR_AGENT](state)

    final_state = nodes[EVIDENCE_ASSEMBLY_AGENT](state)
    structured = final_state["agent_outputs"][EVIDENCE_ASSEMBLY_AGENT]["structured_output"]
    report = final_state["final_report"]

    EvidenceAssemblyOutput.model_validate(structured)
    assert "Customer Behaviour Overview" in report
    assert "Model Risk Explanation" not in report
    assert "Feature Quality Review" not in report
