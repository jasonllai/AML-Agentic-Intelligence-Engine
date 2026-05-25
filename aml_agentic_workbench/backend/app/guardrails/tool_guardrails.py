"""Tool guardrails for safe internal MCP-style access."""

from app.guardrails.schemas import GuardrailDecision, GuardrailStatus
from app.schemas.roles import SupportedRole

BLOCKED_TOOL_PATTERNS = ("shell", "exec", "arbitrary_sql", "raw_sql", "subprocess")
WRITE_ACTION_PATTERNS = ("delete", "update", "insert", "write_external", "send_external")


class ToolGuardrails:
    """Deterministic tool policy checks."""

    def evaluate_tool_call(
        self,
        *,
        tool_name: str,
        role: SupportedRole,
        allowed_roles: set[SupportedRole],
        read_only: bool = True,
    ) -> GuardrailDecision:
        """Evaluate a tool call before execution."""
        lower = tool_name.lower()
        flags: list[str] = []
        if role not in allowed_roles:
            flags.append("role_not_allowed_for_tool")
        if any(pattern in lower for pattern in BLOCKED_TOOL_PATTERNS):
            flags.append("blocked_tool_capability")
        if read_only and any(pattern in lower for pattern in WRITE_ACTION_PATTERNS):
            flags.append("write_tool_requires_approval")
        return GuardrailDecision(
            status=GuardrailStatus.FAILED if flags else GuardrailStatus.PASSED,
            allowed=not flags,
            failure_reasons=flags,
            flags=flags,
        )

