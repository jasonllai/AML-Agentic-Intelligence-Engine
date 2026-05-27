"""Answer relevance judge for system evaluation."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class AnswerRelevanceJudge(BaseJudge):
    """Judge whether the final answer addresses the golden-case query."""

    criterion = JudgeCriterion.ANSWER_RELEVANCE

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        """Evaluate answer relevance using deterministic checks plus LLM rationale."""
        query_terms = {token for token in context.get("query", "").lower().split() if len(token) > 4}
        output_lower = output.lower()
        overlap = sum(1 for token in query_terms if token.strip(".,") in output_lower)
        issues = [] if overlap or not query_terms else ["Output does not address material query terms."]
        score = 0.9 if not issues else 0.45
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Answer the requested role/task question directly before adding supporting evidence."
            if issues
            else None,
            severity=JudgeSeverity.MEDIUM if issues else JudgeSeverity.LOW,
        )
