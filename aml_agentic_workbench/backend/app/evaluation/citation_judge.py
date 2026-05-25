"""Citation judge."""

from typing import Any

from app.evaluation.base import BaseJudge
from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity


class CitationJudge(BaseJudge):
    """Checks whether typology or regulatory claims have citations."""

    criterion = JudgeCriterion.CITATION

    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        lower = output.lower()
        needs_citation = any(term in lower for term in ("typology", "fintrac", "regulatory", "indicator"))
        citations = context.get("citations") or []
        issues = ["Typology or regulatory claim lacks citation."] if needs_citation and not citations else []
        return self._decision(
            score=0.45 if issues else 0.88,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add citations from retrieved AML knowledge documents for typology or regulatory claims.",
            severity=JudgeSeverity.HIGH if issues else JudgeSeverity.LOW,
        )

