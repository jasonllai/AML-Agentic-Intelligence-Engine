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
        if issues:
            score = 0.5
        else:
            agent_outputs = context.get("agent_outputs") or {}
            typology_output = agent_outputs.get("typology_mapping_agent", {})
            score = 0.7
            score += 0.06 if "resembles indicators associated with" in lower else 0.0
            score += 0.05 if context.get("citations") or context.get("documents") else 0.0
            score += 0.04 if "evidence is insufficient" in lower else 0.0
            score += 0.04 if typology_output else 0.0
            try:
                confidence = float(typology_output.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            score += min(0.04, confidence * 0.04)
            score = self._bounded_score(score, upper=0.93)
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Use cautious typology language and identify missing evidence.",
            severity=severity,
        )
