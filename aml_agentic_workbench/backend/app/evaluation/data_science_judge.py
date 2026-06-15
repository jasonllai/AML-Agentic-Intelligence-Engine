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
        if issues:
            score = 0.6
        else:
            model_outputs = context.get("model_outputs") or {}
            agent_outputs = context.get("agent_outputs") or {}
            top_features = model_outputs.get("top_features") if isinstance(model_outputs, dict) else []
            score = 0.72
            score += 0.06 if model_outputs and model_outputs.get("model_version") != "untrained" else 0.0
            score += 0.05 if "not proof" in lower else 0.0
            score += 0.03 if top_features else 0.0
            score += 0.03 if any(agent in agent_outputs for agent in {"model_explanation_agent", "feature_critic_agent"}) else 0.0
            score += 0.02 if "limitations and uncertainty" in lower else 0.0
            score = self._bounded_score(score, upper=0.92)
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add uncertainty language, feature directionality, leakage risk, and validation tests.",
            severity=JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW,
        )
