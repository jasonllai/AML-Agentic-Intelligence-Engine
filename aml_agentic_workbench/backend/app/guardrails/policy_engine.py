"""Central policy engine for AML analysis guardrails."""

from typing import Any

from app.evaluation.judge_panel import JudgePanel
from app.evaluation.judge_schemas import JudgePanelResult
from app.guardrails.approval_gates import ApprovalGate
from app.guardrails.input_guardrails import InputGuardrails
from app.guardrails.output_guardrails import OutputGuardrails
from app.guardrails.schemas import ApprovalDecision, GuardrailDecision, GuardrailStatus


class PolicyEngine:
    """Coordinates deterministic guardrails, LLM judges, and approval gates."""

    def __init__(
        self,
        input_guardrails: InputGuardrails | None = None,
        output_guardrails: OutputGuardrails | None = None,
        judge_panel: JudgePanel | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self.input_guardrails = input_guardrails or InputGuardrails()
        self.output_guardrails = output_guardrails or OutputGuardrails()
        self.judge_panel = judge_panel or JudgePanel()
        self.approval_gate = approval_gate or ApprovalGate()

    def evaluate_input(self, query: str, customer_id: str | None = None, actor: str | None = None) -> GuardrailDecision:
        """Evaluate input before route execution."""
        return self.input_guardrails.evaluate(query, customer_id=customer_id, actor=actor)

    def evaluate_output(
        self,
        *,
        output: str,
        context: dict[str, Any],
        citations: list[dict[str, object]] | None = None,
    ) -> tuple[JudgePanelResult, GuardrailDecision]:
        """Run judge panel and deterministic output policies."""
        judge_result = self.judge_panel.evaluate(output, context)
        guardrail_result = self.output_guardrails.evaluate(output, citations=citations)
        failure_reasons = list(guardrail_result.failure_reasons)
        if judge_result.pass_fail == "fail":
            failure_reasons.append(judge_result.failure_reason or "judge_panel_failed")
        allowed = guardrail_result.allowed and judge_result.pass_fail == "pass"
        status = GuardrailStatus.PASSED if allowed else GuardrailStatus.FAILED
        decision = GuardrailDecision(
            status=status,
            allowed=allowed,
            failure_reasons=failure_reasons,
            flags=[*guardrail_result.flags, *([] if judge_result.pass_fail == "pass" else ["judge_panel_failed"])],
            safe_output=guardrail_result.safe_output,
            audit_only_output=guardrail_result.audit_only_output or (output if not allowed else None),
        )
        return judge_result, decision

    def approval_for_action(self, action: str, approved: bool | None = None) -> ApprovalDecision:
        """Evaluate human approval requirements for a sensitive action."""
        return self.approval_gate.evaluate(action, approved=approved)

