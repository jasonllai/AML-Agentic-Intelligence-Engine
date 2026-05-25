"""Backward-compatible policy guardrail facade."""

from app.guardrails.schemas import GuardrailDecision, GuardrailStatus


class GuardrailPolicy:
    """Initial guardrail policy facade."""

    def evaluate_query(self, query: str) -> GuardrailDecision:
        """Evaluate a user query for obvious policy flags."""
        flags: list[str] = []
        if not query.strip():
            flags.append("empty_query")
        return GuardrailDecision(
            status=GuardrailStatus.PASSED if not flags else GuardrailStatus.FAILED,
            allowed=not flags,
            flags=flags,
            failure_reasons=flags,
        )
