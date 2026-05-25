"""Output guardrails and safe rewrite logic."""

from app.guardrails.pii_guardrails import PIIGuardrails
from app.guardrails.schemas import GuardrailDecision, GuardrailStatus

PROHIBITED_OUTPUT_PHRASES = (
    "this customer is laundering money",
    "the customer is laundering money",
    "criminal activity confirmed",
    "file an str",
)

ALLOWED_SAFER_PHRASES = (
    "resembles indicators associated with",
    "may warrant further review",
    "model-driven risk signal",
    "evidence is insufficient to conclude",
    "requires human review before action",
)


class OutputGuardrails:
    """Deterministic output policy enforcement."""

    def __init__(self, pii_guardrails: PIIGuardrails | None = None) -> None:
        self.pii_guardrails = pii_guardrails or PIIGuardrails()

    def evaluate(self, output: str, citations: list[dict[str, object]] | None = None) -> GuardrailDecision:
        """Evaluate and potentially rewrite final output."""
        lower = output.lower()
        flags: list[str] = []
        for phrase in PROHIBITED_OUTPUT_PHRASES:
            if phrase in lower:
                flags.append(f"prohibited_phrase:{phrase}")
        if "typology" in lower and not citations:
            flags.append("unsupported_typology_claim")
        if "citation:" in lower and not citations:
            flags.append("fabricated_citation_risk")
        if "model score proves" in lower or "score proves" in lower:
            flags.append("model_score_treated_as_proof")
        pii_flags = self.pii_guardrails.detect(output)
        if pii_flags:
            flags.extend([f"pii:{flag}" for flag in pii_flags])

        safe_output = self._safe_rewrite(output) if flags else self.pii_guardrails.redact(output)
        return GuardrailDecision(
            status=GuardrailStatus.REWRITTEN if flags else GuardrailStatus.PASSED,
            allowed=not any(flag.startswith("prohibited_phrase") for flag in flags),
            failure_reasons=flags,
            flags=flags,
            safe_output=safe_output,
            audit_only_output=output if flags else None,
        )

    def _safe_rewrite(self, output: str) -> str:
        rewritten = output
        replacements = {
            "this customer is laundering money": "the behaviour resembles indicators associated with AML risk",
            "the customer is laundering money": "the behaviour resembles indicators associated with AML risk",
            "criminal activity confirmed": "evidence is insufficient to conclude criminal activity",
            "file an STR": "requires human review before action",
            "file an str": "requires human review before action",
            "model score proves": "model-driven risk signal suggests",
            "score proves": "model-driven risk signal suggests",
        }
        for source, target in replacements.items():
            rewritten = rewritten.replace(source, target)
        redacted = self.pii_guardrails.redact(rewritten)
        if not any(phrase in redacted.lower() for phrase in ALLOWED_SAFER_PHRASES):
            redacted += "\n\nEvidence is insufficient to conclude; this requires human review before action."
        return redacted

