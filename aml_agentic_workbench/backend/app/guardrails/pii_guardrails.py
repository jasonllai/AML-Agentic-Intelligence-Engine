"""PII guardrails."""

import re

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SIN_PATTERN = re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b")


class PIIGuardrails:
    """PII detection and redaction helpers."""

    def detect(self, text: str) -> list[str]:
        """Return detected PII categories."""
        flags: list[str] = []
        if EMAIL_PATTERN.search(text):
            flags.append("email")
        if PHONE_PATTERN.search(text):
            flags.append("phone")
        if SIN_PATTERN.search(text):
            flags.append("sin_like_identifier")
        return flags

    def redact(self, text: str) -> str:
        """Redact common PII patterns."""
        redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
        redacted = SIN_PATTERN.sub("[REDACTED_IDENTIFIER]", redacted)
        return redacted

