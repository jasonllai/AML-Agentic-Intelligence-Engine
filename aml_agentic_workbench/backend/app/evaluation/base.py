"""Shared judge utilities."""

import json
from abc import ABC, abstractmethod
from typing import Any

from app.evaluation.judge_schemas import JudgeCriterion, JudgeDecision, JudgeSeverity
from app.llm.client import LLMClient, get_llm_client


class BaseJudge(ABC):
    """Base class for LLM-assisted judges with deterministic policy checks."""

    criterion: JudgeCriterion

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()

    @abstractmethod
    def evaluate(self, output: str, context: dict[str, Any]) -> JudgeDecision:
        """Evaluate output with context."""

    def _llm_rationale(self, output: str, context: dict[str, Any]) -> str:
        prompt = (
            f"You are the {self.criterion.value} judge for a bank AML system. "
            "Review the output and context. Provide a concise rationale only.\n"
            f"Output: {output[:4000]}\nContext: {json.dumps(context, default=str)[:4000]}"
        )
        return self.llm_client.generate_text(prompt)

    def _decision(
        self,
        *,
        score: float,
        issues: list[str],
        explanation: str,
        recommended_fix: str | None = None,
        severity: JudgeSeverity = JudgeSeverity.LOW,
        threshold: float = 0.7,
    ) -> JudgeDecision:
        passed = score >= threshold and severity not in {JudgeSeverity.HIGH, JudgeSeverity.CRITICAL}
        return JudgeDecision(
            criterion=self.criterion,
            score=round(score, 3),
            pass_fail="pass" if passed else "fail",
            explanation=explanation,
            detected_issues=issues,
            recommended_fix=recommended_fix,
            severity=severity,
        )
