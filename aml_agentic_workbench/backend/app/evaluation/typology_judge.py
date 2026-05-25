"""Typology mapping judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class TypologyJudge(BaseJudge):
    """Checks whether typology mapping is reasonable and not overextended."""

    criterion = JudgeCriterion.TYPOLOGY

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        lower = output.lower()
        issues: list[str] = []
        if "is laundering" in lower or "criminal activity confirmed" in lower:
            issues.append("Typology mapping is overextended into a legal conclusion.")
        if "resembles indicators associated with" not in lower and "typology" in lower:
            issues.append("Typology mapping should use careful resemblance language.")
        severity = JudgeSeverity.HIGH if issues else JudgeSeverity.LOW
        return self._decision(
            score=0.5 if issues else 0.84,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Use cautious typology language and identify missing evidence.",
            severity=severity,
        )

