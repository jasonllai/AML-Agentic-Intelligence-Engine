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
        if issues:
            score = 0.45
        else:
            documents = context.get("documents") or []
            cited_urls = [citation.get("url") for citation in citations if isinstance(citation, dict) and citation.get("url")]
            score = 0.72
            score += min(0.12, 0.04 * len(citations)) if citations else 0.0
            score += 0.04 if documents else 0.0
            score += 0.03 if cited_urls else 0.0
            score += 0.03 if "typology mapping" in lower else 0.0
            score += 0.05 if not needs_citation else 0.0
            score = self._bounded_score(score)
        return self._decision(
            score=score,
            issues=issues,
            explanation=self._llm_rationale(output, context),
            recommended_fix="Add citations from retrieved AML knowledge documents for typology or regulatory claims.",
            severity=JudgeSeverity.HIGH if issues else JudgeSeverity.LOW,
        )
