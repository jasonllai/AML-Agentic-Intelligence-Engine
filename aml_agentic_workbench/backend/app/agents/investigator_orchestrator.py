"""Bounded investigator supervisor and critic orchestration."""

from collections.abc import Iterator
from typing import Any

from app.agents.nodes import AgentNode, make_agent_nodes
from app.agents.router import (
    CASE_INVESTIGATION_AGENT,
    EVIDENCE_ASSEMBLY_AGENT,
    GUARDRAIL_AGENT,
    JUDGE_PANEL_AGENT,
    REPORT_CRITIC_AGENT,
    SUPERVISOR_PLANNER_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import AMLAgentState
from app.schemas.roles import SupportedRole

FINALIZE_REPORT = "finalize_report"
INVESTIGATOR_AGENTIC_TASK = "investigate_model_prioritized_candidate"
EVIDENCE_ACTIONS: tuple[str, ...] = (
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
    CASE_INVESTIGATION_AGENT,
)
PLANNER_ALLOWED_ACTIONS: tuple[str, ...] = (*EVIDENCE_ACTIONS, FINALIZE_REPORT)
MAX_PLANNER_STEPS = 6
MAX_REFINEMENT_ROUNDS = 1
MAX_GUARDRAIL_REMEDIATION_ROUNDS = 1
NON_REMEDIABLE_GUARDRAIL_FLAGS = {"empty_query", "no_agent_outputs"}


class InvestigatorAgenticRunner:
    """Run the primary Investigator workflow with planner and critic checkpoints."""

    def __init__(
        self,
        node_registry: dict[str, AgentNode] | None = None,
        *,
        max_planner_steps: int = MAX_PLANNER_STEPS,
        max_refinement_rounds: int = MAX_REFINEMENT_ROUNDS,
        max_guardrail_remediation_rounds: int = MAX_GUARDRAIL_REMEDIATION_ROUNDS,
    ) -> None:
        self.node_registry = node_registry or make_agent_nodes()
        self.max_planner_steps = max_planner_steps
        self.max_refinement_rounds = max_refinement_rounds
        self.max_guardrail_remediation_rounds = max_guardrail_remediation_rounds
        self.state: AMLAgentState = AMLAgentState()

    def run(self, state: AMLAgentState) -> Iterator[dict[str, Any]]:
        """Execute the investigator loop and yield live stream events."""
        self.state = state
        self._ensure_agentic_route()
        yield self._event("run_started", route=self.state.get("route", []))

        for _ in range(self.max_planner_steps):
            self.state = self.node_registry[SUPERVISOR_PLANNER_AGENT](self.state)
            decision = self._validated_latest_decision()
            yield self._event("planner_decision", decision=decision)

            next_action = decision["next_action"]
            if next_action == FINALIZE_REPORT:
                self.state["stop_reason"] = decision.get("stop_reason") or "Planner finalized evidence gathering."
                break

            yield from self._run_agent(next_action)
        else:
            self.state["stop_reason"] = "Max planner steps reached; finalizing with available evidence."

        yield from self._run_agent(EVIDENCE_ASSEMBLY_AGENT)

        yield self._event("critic_started", agent=REPORT_CRITIC_AGENT)
        self.state = self.node_registry[REPORT_CRITIC_AGENT](self.state)
        critic_review = self.state.get("critic_reviews", [])[-1]
        yield self._event("critic_completed", agent=REPORT_CRITIC_AGENT, review=critic_review)

        if critic_review.get("must_refine") and self.state.get("refinement_rounds", 0) < self.max_refinement_rounds:
            self.state["refinement_rounds"] = self.state.get("refinement_rounds", 0) + 1
            yield self._event(
                "refinement_started",
                agent=EVIDENCE_ASSEMBLY_AGENT,
                instruction=critic_review.get("refinement_instruction"),
            )
            self.state = self.node_registry[EVIDENCE_ASSEMBLY_AGENT](self.state)
            yield self._event(
                "refinement_completed",
                agent=EVIDENCE_ASSEMBLY_AGENT,
                output=self.state.get("agent_outputs", {}).get(EVIDENCE_ASSEMBLY_AGENT, {}),
                refinement_rounds=self.state.get("refinement_rounds", 0),
            )

        yield from self._run_final_governance()
        if self._should_remediate_guardrail():
            yield from self._run_guardrail_remediation()
            yield from self._run_final_governance()

    def _run_final_governance(self) -> Iterator[dict[str, Any]]:
        yield self._event("judge_started", agent=JUDGE_PANEL_AGENT)
        self.state = self.node_registry[JUDGE_PANEL_AGENT](self.state)
        yield self._event("agent_completed", agent=JUDGE_PANEL_AGENT, output=self._agent_output(JUDGE_PANEL_AGENT))

        yield self._event("guardrail_started", agent=GUARDRAIL_AGENT)
        self.state = self.node_registry[GUARDRAIL_AGENT](self.state)
        yield self._event("agent_completed", agent=GUARDRAIL_AGENT, output=self._agent_output(GUARDRAIL_AGENT))

    def _should_remediate_guardrail(self) -> bool:
        if self.state.get("guardrail_remediation_rounds", 0) >= self.max_guardrail_remediation_rounds:
            return False
        flags = list(self.state.get("guardrail_flags", []))
        if not flags:
            return False
        if any(flag in NON_REMEDIABLE_GUARDRAIL_FLAGS for flag in flags):
            return False
        return True

    def _run_guardrail_remediation(self) -> Iterator[dict[str, Any]]:
        next_round = self.state.get("guardrail_remediation_rounds", 0) + 1
        flags = list(self.state.get("guardrail_flags", []))
        remediation = {
            "round": next_round,
            "flags": flags,
            "judge_failure_reason": self.state.get("judge_panel_result", {}).get("failure_reason"),
            "instruction": self._build_guardrail_remediation_instruction(flags),
            "status": "started",
        }
        self.state["guardrail_remediation_instruction"] = remediation["instruction"]
        self.state["guardrail_remediations"] = [*self.state.get("guardrail_remediations", []), remediation]

        yield self._event(
            "guardrail_remediation_started",
            flags=flags,
            instruction=remediation["instruction"],
            guardrail_remediation_rounds=next_round,
        )

        yield self._event("critic_started", agent=REPORT_CRITIC_AGENT, instruction=remediation["instruction"])
        self.state = self.node_registry[REPORT_CRITIC_AGENT](self.state)
        critic_review = self.state.get("critic_reviews", [])[-1]
        yield self._event("critic_completed", agent=REPORT_CRITIC_AGENT, review=critic_review)

        self.state["guardrail_remediation_rounds"] = next_round
        self.state = self.node_registry[EVIDENCE_ASSEMBLY_AGENT](self.state)
        completed = {**remediation, "status": "completed"}
        self.state["guardrail_remediations"] = [*self.state.get("guardrail_remediations", [])[:-1], completed]
        yield self._event(
            "guardrail_remediation_completed",
            agent=EVIDENCE_ASSEMBLY_AGENT,
            output=self._agent_output(EVIDENCE_ASSEMBLY_AGENT),
            guardrail_remediation_rounds=next_round,
        )

    def _build_guardrail_remediation_instruction(self, flags: list[str]) -> str:
        reason = self.state.get("judge_panel_result", {}).get("failure_reason")
        issues = ", ".join(flags) if flags else reason or "final governance failure"
        return (
            "Revise the draft report using only evidence already gathered. Address these governance issues: "
            f"{issues}. Remove prohibited or conclusive AML language, avoid treating model scores as proof, "
            "redact PII, remove fabricated citations or unsupported typology claims, avoid premature case "
            "disposition, justify any disposition recommendation with existing evidence, and preserve human-review "
            "and model-prioritization-only language before the final Judge Panel and Guardrail review."
        )

    def _ensure_agentic_route(self) -> None:
        if self.state.get("route"):
            return
        self.state["route"] = [
            SUPERVISOR_PLANNER_AGENT,
            *EVIDENCE_ACTIONS,
            EVIDENCE_ASSEMBLY_AGENT,
            REPORT_CRITIC_AGENT,
            JUDGE_PANEL_AGENT,
            GUARDRAIL_AGENT,
        ]

    def _validated_latest_decision(self) -> dict[str, Any]:
        decisions = self.state.get("planner_decisions", [])
        decision = dict(decisions[-1]) if decisions else {}
        proposed_action = str(decision.get("next_action", ""))
        required_action = self._next_required_action()
        if proposed_action not in PLANNER_ALLOWED_ACTIONS:
            decision = self._override_decision(
                decision,
                required_action,
                f"Planner returned invalid action: {proposed_action}",
            )
        elif proposed_action != required_action:
            decision = self._override_decision(
                decision,
                required_action,
                f"Planner action {proposed_action} was overridden by bounded investigator policy.",
            )
        if decision["next_action"] == FINALIZE_REPORT and not decision.get("stop_reason"):
            decision["stop_reason"] = "Required investigator evidence is available."
        self.state["planner_decisions"] = [*decisions[:-1], decision]
        return decision

    def _override_decision(self, decision: dict[str, Any], next_action: str, reason: str) -> dict[str, Any]:
        updated = {
            **decision,
            "next_action": next_action,
            "reason": f"{decision.get('reason', 'No planner reason supplied')} {reason}",
            "policy_override": True,
        }
        if next_action == FINALIZE_REPORT:
            updated["stop_reason"] = "Required investigator evidence is available."
        self.state["audit_trace"] = [
            *self.state.get("audit_trace", []),
            {
                "event": "planner_policy_override",
                "agent": SUPERVISOR_PLANNER_AGENT,
                "requested_action": decision.get("next_action"),
                "next_action": next_action,
            },
        ]
        return updated

    def _next_required_action(self) -> str:
        outputs = self.state.get("agent_outputs", {})
        for action in EVIDENCE_ACTIONS:
            if action not in outputs:
                return action
        return FINALIZE_REPORT

    def _run_agent(self, agent: str) -> Iterator[dict[str, Any]]:
        yield self._event("agent_started", agent=agent)
        self.state = self.node_registry[agent](self.state)
        yield self._event("agent_completed", agent=agent, output=self._agent_output(agent))

    def _agent_output(self, agent: str) -> dict[str, Any]:
        return self.state.get("agent_outputs", {}).get(agent, {})

    def _event(self, event_name: str, **payload: Any) -> dict[str, Any]:
        event = {"event": event_name, **payload}
        self.state["stream_events"] = [*self.state.get("stream_events", []), event]
        return event


def is_primary_investigator_agentic_request(
    role: SupportedRole,
    task_type: str,
    selected_agents: list[str] | None = None,
) -> bool:
    """Return whether a request should use the bounded Investigator agentic runner."""
    return (
        role == SupportedRole.INVESTIGATOR
        and task_type == INVESTIGATOR_AGENTIC_TASK
        and not selected_agents
    )
