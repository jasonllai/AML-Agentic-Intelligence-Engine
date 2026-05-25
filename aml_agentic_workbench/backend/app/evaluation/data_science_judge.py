"""Data science judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class DataScienceJudge(BaseJudge):
    """Checks technical correctness of feature and model explanations."""

    criterion = JudgeCriterion.DATA_SCIENCE

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        lower = output.lower()
        issues: list[str] = []
        if "model score" in lower and "not proof" not in lower:
            issues.append("Model score is discussed without uncertainty/proof caveat.")
        if "pyspark" in lower and "required_columns" in lower and "leakage" not in lower:
            issues.append("Feature recommendation lacks leakage discussion.")
        return self._decision(
            score=0.6 if issues else 0.82,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add uncertainty language, feature directionality, leakage risk, and validation tests.",
            severity=JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW,
        )

