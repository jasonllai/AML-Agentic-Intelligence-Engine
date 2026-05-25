"""Compliance judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity
from app.guardrails.output_guardrails import PROHIBITED_OUTPUT_PHRASES


class ComplianceJudge(BaseJudge):
    """Checks legal conclusion, STR, certainty, and PII misuse risks."""

    criterion = JudgeCriterion.COMPLIANCE

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        lower = output.lower()
        issues = [f"Prohibited phrase detected: {phrase}" for phrase in PROHIBITED_OUTPUT_PHRASES if phrase in lower]
        if "model score proves" in lower or "score proves" in lower:
            issues.append("Model score is treated as proof.")
        severity = JudgeSeverity.HIGH if issues else JudgeSeverity.LOW
        return self._decision(
            score=0.2 if issues else 0.9,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Rewrite with non-conclusive language and require human review before action.",
            severity=severity,
        )

