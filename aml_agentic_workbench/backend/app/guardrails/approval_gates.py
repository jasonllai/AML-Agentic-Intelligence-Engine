"""Human approval gates for sensitive actions."""

from app.guardrails.schemas import ApprovalDecision, ApprovalStatus

SENSITIVE_ACTIONS = {
    "export_report",
    "send_report_external",
    "str_like_narrative_generation",
    "case_escalation",
    "external_database_write",
    "database_write_beyond_audit_or_report",
}


class ApprovalGate:
    """Determines whether a requested action needs human approval."""

    def evaluate(self, action: str, approved: bool | None = None) -> ApprovalDecision:
        """Return approval status for an action."""
        if action not in SENSITIVE_ACTIONS:
            return ApprovalDecision(action=action, status=ApprovalStatus.NOT_REQUIRED)
        if approved is True:
            return ApprovalDecision(action=action, status=ApprovalStatus.APPROVED)
        if approved is False:
            return ApprovalDecision(
                action=action,
                status=ApprovalStatus.REJECTED,
                reason="Human approver rejected action.",
            )
        return ApprovalDecision(
            action=action,
            status=ApprovalStatus.PENDING,
            reason="Sensitive action requires human approval before execution.",
        )
