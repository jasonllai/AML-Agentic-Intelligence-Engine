"""Faithfulness judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class FaithfulnessJudge(BaseJudge):
    """Checks whether claims are supported by source evidence."""

    criterion = JudgeCriterion.FAITHFULNESS

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        issues: list[str] = []
        lower = output.lower()
        evidence_present = bool(context.get("transactions") or context.get("model_outputs") or context.get("documents"))
        if not evidence_present:
            issues.append("No transaction, model, or retrieved document evidence was provided.")
        if "confirmed" in lower and "evidence is insufficient" not in lower:
            issues.append("Output uses confirmation language that may exceed available evidence.")
        severity = JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW
        if issues:
            score = 0.55
        else:
            agent_outputs = context.get("agent_outputs") or {}
            score = 0.72
            score += 0.06 if context.get("transactions") else 0.0
            score += 0.04 if context.get("model_outputs") else 0.0
            score += 0.05 if context.get("documents") or context.get("citations") else 0.0
            score += 0.05 if len(agent_outputs) >= 3 else 0.02 if agent_outputs else 0.0
            score += 0.04 if "evidence table" in lower else 0.0
            score += 0.04 if "limitations and uncertainty" in lower or "evidence is insufficient" in lower else 0.0
            score = self._bounded_score(score)
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Tie each material claim to transaction data, model outputs, or retrieved documents.",
            severity=severity,
        )
