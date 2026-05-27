"""Input guardrails for analysis requests."""

from app.guardrails.schemas import GuardrailDecision, GuardrailStatus

PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore prior instructions",
    "fabricate suspicious activity evidence",
    "fabricate evidence",
    "developer message",
    "system prompt",
    "reveal your prompt",
    "print your instructions",
    "bypass guardrails",
)

UNSAFE_OR_IRRELEVANT_PATTERNS = (
    "how to launder",
    "evade fintrac",
    "hide suspicious activity",
    "write malware",
)


class InputGuardrails:
    """Deterministic input policy checks."""

    def evaluate(self, query: str, customer_id: str | None = None, actor: str | None = None) -> GuardrailDecision:
        """Evaluate a user query before routing."""
        lower = query.lower()
        flags: list[str] = []
        if any(pattern in lower for pattern in PROMPT_INJECTION_PATTERNS):
            flags.append("prompt_injection_or_prompt_extraction")
        if any(pattern in lower for pattern in UNSAFE_OR_IRRELEVANT_PATTERNS):
            flags.append("unsafe_or_irrelevant_request")
        if customer_id and actor and actor not in {"system", "test"}:
            flags.append("unauthorized_customer_access_placeholder")
        return GuardrailDecision(
            status=GuardrailStatus.FAILED if flags else GuardrailStatus.PASSED,
            allowed=not flags,
            failure_reasons=flags,
            flags=flags,
            safe_output=(
                "Request blocked by input policy. Rephrase the AML analysis request without prompt extraction, "
                "unsafe instructions, or unauthorized access."
                if flags
                else None
            ),
        )
