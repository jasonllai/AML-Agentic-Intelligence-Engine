"""Judge panel scoring tests."""

from app.evaluation.judge_panel import JudgePanel
from app.evaluation.judge_schemas import JudgeCriterion
from app.llm.mock_client import MockLLMClient


def test_judge_panel_scores_change_with_evidence_quality() -> None:
    """Passing reports should still score differently when evidence quality differs."""
    panel = JudgePanel(llm_client=MockLLMClient())
    rich_report = (
        "# AML Intelligence Report\n"
        "## Typology Mapping\n"
        "The activity resembles indicators associated with rapid movement of funds.\n"
        "## Evidence Table\n"
        "Transaction, model, typology, and case review evidence were considered.\n"
        "## Limitations and Uncertainty\n"
        "Model score is not proof, and evidence is insufficient to conclude suspicious activity.\n"
        "## Recommended Analytical Next Steps\n"
        "Review KYC purpose of funds and source-of-funds documentation."
    )
    thin_report = (
        "# AML Intelligence Report\n"
        "## Typology Mapping\n"
        "The activity resembles indicators associated with rapid movement of funds.\n"
        "## Recommended Analytical Next Steps\n"
        "Review the case."
    )

    rich = panel.evaluate(
        rich_report,
        {
            "transactions": [{"transaction_id": "T1"}, {"transaction_id": "T2"}],
            "model_outputs": {"risk_score": 0.81, "top_features": ["txn_count_total"]},
            "documents": [{"doc_id": "fintrac:1"}],
            "citations": [{"url": "https://fintrac-canafe.canada.ca/"}],
            "agent_outputs": {
                "transaction_behaviour_agent": {"confidence": 0.82, "evidence": [{"source": "transactions"}]},
                "typology_mapping_agent": {"confidence": 0.72, "citations": [{"url": "https://fintrac-canafe.canada.ca/"}]},
                "case_investigation_agent": {"confidence": 0.76, "evidence": [{"source": "case_review"}]},
            },
        },
    )
    thin = panel.evaluate(
        thin_report,
        {
            "transactions": [{"transaction_id": "T1"}],
            "documents": [{"doc_id": "fintrac:1"}],
            "citations": [{"url": "https://fintrac-canafe.canada.ca/"}],
            "agent_outputs": {
                "typology_mapping_agent": {"confidence": 0.55, "citations": [{"url": "https://fintrac-canafe.canada.ca/"}]}
            },
        },
    )

    assert rich.overall_score != thin.overall_score
    assert rich.decisions[JudgeCriterion.FAITHFULNESS].score > thin.decisions[JudgeCriterion.FAITHFULNESS].score
    assert rich.decisions[JudgeCriterion.USEFULNESS].score > thin.decisions[JudgeCriterion.USEFULNESS].score
