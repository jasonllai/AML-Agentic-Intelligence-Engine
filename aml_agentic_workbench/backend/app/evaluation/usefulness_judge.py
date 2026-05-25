"""Usefulness judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class UsefulnessJudge(BaseJudge):
    """Checks whether output is clear, role-appropriate, and actionable."""

    criterion = JudgeCriterion.USEFULNESS

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        issues: list[str] = []
        if len(output.strip()) < 120:
            issues.append("Output is too short to support review.")
        if "Recommended Analytical Next Steps" not in output and "next step" not in output.lower():
            issues.append("Output lacks actionable next steps.")
        return self._decision(
            score=0.62 if issues else 0.84,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add concise role-appropriate next steps and explain decision-use limits.",
            severity=JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW,
            threshold=0.6,
        )

