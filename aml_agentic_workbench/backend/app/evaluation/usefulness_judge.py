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
        agent_outputs = context.get("agent_outputs") or {}
        score = 0.66
        length = len(output.strip())
        score += 0.06 if length >= 350 else 0.04 if length >= 200 else 0.02 if length >= 120 else 0.0
        score += 0.05 if "Recommended Analytical Next Steps" in output or "next step" in output.lower() else 0.0
        score += 0.05 if "Evidence Table" in output else 0.0
        score += 0.05 if "Limitations and Uncertainty" in output else 0.0
        score += 0.05 if len(agent_outputs) >= 3 else 0.02 if agent_outputs else 0.0
        if issues:
            score -= 0.12
        score = self._bounded_score(score, upper=0.93)
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add concise role-appropriate next steps and explain decision-use limits.",
            severity=JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW,
            threshold=0.6,
        )
