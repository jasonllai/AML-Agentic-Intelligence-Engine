"""Judge panel aggregation."""

from typing import Any

from app.evaluation.citation_judge import CitationJudge
from app.evaluation.compliance_judge import ComplianceJudge
from app.evaluation.data_science_judge import DataScienceJudge
from app.evaluation.faithfulness_judge import FaithfulnessJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgePanelResult, JudgeSeverity
from app.evaluation.typology_judge import TypologyJudge
from app.evaluation.usefulness_judge import UsefulnessJudge
from app.llm.client import LLMClient

WEIGHTS: dict[JudgeCriterion, float] = {
    JudgeCriterion.FAITHFULNESS: 0.25,
    JudgeCriterion.CITATION: 0.20,
    JudgeCriterion.COMPLIANCE: 0.20,
    JudgeCriterion.TYPOLOGY: 0.15,
    JudgeCriterion.DATA_SCIENCE: 0.10,
    JudgeCriterion.USEFULNESS: 0.10,
}


class JudgePanel:
    """Runs all judges and aggregates bank-grade quality gates."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.judges = [
            FaithfulnessJudge(llm_client),
            CitationJudge(llm_client),
            ComplianceJudge(llm_client),
            TypologyJudge(llm_client),
            DataScienceJudge(llm_client),
            UsefulnessJudge(llm_client),
        ]

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgePanelResult:
        """Evaluate output and apply weighted aggregation."""
        decisions = {judge.criterion: judge.evaluate(output, context) for judge in self.judges}
        overall = round(sum(decisions[criterion].score * weight for criterion, weight in WEIGHTS.items()), 3)
        compliance = decisions[JudgeCriterion.COMPLIANCE]
        override_fail = compliance.pass_fail == "fail" and compliance.severity in {
            JudgeSeverity.HIGH,
            JudgeSeverity.CRITICAL,
        }
        pass_fail = "fail" if override_fail or overall < 0.7 else "pass"
        failure_reason = None
        if override_fail:
            failure_reason = "Compliance judge failed with high severity."
        elif overall < 0.7:
            failure_reason = "Aggregate judge score is below threshold."
        return JudgePanelResult(
            decisions=decisions,
            overall_score=overall,
            pass_fail=pass_fail,
            failure_reason=failure_reason,
        )
