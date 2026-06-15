"""Role-aware dynamic routing for AML agent execution."""

from pydantic import BaseModel, Field

from app.core.constants import SUPPORTED_TASK_TYPES
from app.schemas.roles import SupportedRole

TRANSACTION_BEHAVIOUR_AGENT = "transaction_behaviour_agent"
MODEL_EXPLANATION_AGENT = "model_explanation_agent"
TYPOLOGY_MAPPING_AGENT = "typology_mapping_agent"
FEATURE_CRITIC_AGENT = "feature_critic_agent"
CANDIDATE_RANKING_AGENT = "candidate_ranking_agent"
CASE_INVESTIGATION_AGENT = "case_investigation_agent"
EVIDENCE_ASSEMBLY_AGENT = "evidence_assembly_agent"
GUARDRAIL_AGENT = "guardrail_agent"
JUDGE_PANEL_AGENT = "judge_panel_agent"

SUPPORTED_AGENTS: tuple[str, ...] = (
    TRANSACTION_BEHAVIOUR_AGENT,
    MODEL_EXPLANATION_AGENT,
    TYPOLOGY_MAPPING_AGENT,
    FEATURE_CRITIC_AGENT,
    CANDIDATE_RANKING_AGENT,
    CASE_INVESTIGATION_AGENT,
    EVIDENCE_ASSEMBLY_AGENT,
    GUARDRAIL_AGENT,
    JUDGE_PANEL_AGENT,
)

MANDATORY_FINAL_AGENT = GUARDRAIL_AGENT

ROLE_AGENT_PERMISSIONS: dict[SupportedRole, set[str]] = {
    SupportedRole.DATA_SCIENTIST: {
        TRANSACTION_BEHAVIOUR_AGENT,
        MODEL_EXPLANATION_AGENT,
        FEATURE_CRITIC_AGENT,
        CANDIDATE_RANKING_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    },
    SupportedRole.INVESTIGATOR: {
        TRANSACTION_BEHAVIOUR_AGENT,
        TYPOLOGY_MAPPING_AGENT,
        CASE_INVESTIGATION_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    },
    SupportedRole.MODEL_VALIDATOR: {
        MODEL_EXPLANATION_AGENT,
        FEATURE_CRITIC_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    },
    SupportedRole.COMPLIANCE_STRATEGY: {
        TYPOLOGY_MAPPING_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    },
}

FULL_INTELLIGENCE_ROUTE: tuple[str, ...] = (
    TRANSACTION_BEHAVIOUR_AGENT,
    MODEL_EXPLANATION_AGENT,
    TYPOLOGY_MAPPING_AGENT,
    FEATURE_CRITIC_AGENT,
    EVIDENCE_ASSEMBLY_AGENT,
    JUDGE_PANEL_AGENT,
    GUARDRAIL_AGENT,
)

ROUTE_TABLE: dict[tuple[SupportedRole, str], tuple[str, ...]] = {
    (SupportedRole.DATA_SCIENTIST, "generate_model_driven_candidates"): (
        CANDIDATE_RANKING_AGENT,
    ),
    (SupportedRole.INVESTIGATOR, "investigate_model_prioritized_candidate"): (
        TRANSACTION_BEHAVIOUR_AGENT,
        TYPOLOGY_MAPPING_AGENT,
        CASE_INVESTIGATION_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    (SupportedRole.DATA_SCIENTIST, "model_risk_explanation"): (
        TRANSACTION_BEHAVIOUR_AGENT,
        MODEL_EXPLANATION_AGENT,
        FEATURE_CRITIC_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    (SupportedRole.INVESTIGATOR, "investigator_summary"): (
        TRANSACTION_BEHAVIOUR_AGENT,
        TYPOLOGY_MAPPING_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    (SupportedRole.MODEL_VALIDATOR, "model_validation_review"): (
        MODEL_EXPLANATION_AGENT,
        FEATURE_CRITIC_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    (SupportedRole.COMPLIANCE_STRATEGY, "compliance_typology_review"): (
        TYPOLOGY_MAPPING_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
}

TASK_FALLBACK_ROUTES: dict[str, tuple[str, ...]] = {
    "generate_model_driven_candidates": (
        CANDIDATE_RANKING_AGENT,
    ),
    "investigate_model_prioritized_candidate": (
        TRANSACTION_BEHAVIOUR_AGENT,
        TYPOLOGY_MAPPING_AGENT,
        CASE_INVESTIGATION_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    "customer_behaviour_analysis": (
        TRANSACTION_BEHAVIOUR_AGENT,
        EVIDENCE_ASSEMBLY_AGENT,
        JUDGE_PANEL_AGENT,
        GUARDRAIL_AGENT,
    ),
    "typology_mapping": (TYPOLOGY_MAPPING_AGENT, EVIDENCE_ASSEMBLY_AGENT, JUDGE_PANEL_AGENT, GUARDRAIL_AGENT),
    "feature_quality_review": (FEATURE_CRITIC_AGENT, EVIDENCE_ASSEMBLY_AGENT, JUDGE_PANEL_AGENT, GUARDRAIL_AGENT),
    "model_risk_explanation": (MODEL_EXPLANATION_AGENT, EVIDENCE_ASSEMBLY_AGENT, JUDGE_PANEL_AGENT, GUARDRAIL_AGENT),
}


class RouteValidationError(ValueError):
    """Raised when a requested route is invalid or unauthorized."""


class AgentRoute(BaseModel):
    """Resolved route for one analysis request."""

    role: SupportedRole
    task_type: str
    query: str
    agents: list[str] = Field(..., min_length=1)
    selected_agents: list[str] | None = None
    is_partial: bool = False
    explanation: str


class RoleAwareRouter:
    """Select the minimal necessary AML agents for a role and task.

    Partial-agent execution is intentional: running only the required agents
    reduces latency, compute cost, and unnecessary data exposure. It also lowers
    operational risk by limiting each request to the smallest useful workflow.
    """

    def route(
        self,
        role: SupportedRole,
        task_type: str,
        query: str,
        selected_agents: list[str] | None = None,
    ) -> AgentRoute:
        """Resolve an agent route from role, task, query, and optional explicit selection."""
        if task_type not in SUPPORTED_TASK_TYPES:
            raise RouteValidationError(f"Unsupported task_type '{task_type}'.")

        normalized_selection = self._normalize_selected_agents(selected_agents)
        if normalized_selection:
            agents = self._with_mandatory_guardrail(normalized_selection)
            route = AgentRoute(
                role=role,
                task_type=task_type,
                query=query,
                agents=agents,
                selected_agents=normalized_selection,
                is_partial=True,
                explanation=(
                    "Partial route selected by caller; registry validated requested agents and appended "
                    "mandatory guardrail_agent for governed execution."
                ),
            )
            self.validate_route(route)
            return route

        if task_type == "full_intelligence_report":
            agents = list(FULL_INTELLIGENCE_ROUTE)
        else:
            agents = list(ROUTE_TABLE.get((role, task_type), TASK_FALLBACK_ROUTES.get(task_type, ())))
            agents = self._filter_to_role_permissions(role, agents)
            agents = self._with_mandatory_guardrail(agents)

        route = AgentRoute(
            role=role,
            task_type=task_type,
            query=query,
            agents=agents,
            is_partial=False,
            explanation=self._build_explanation(role, task_type, agents),
        )
        self.validate_route(route)
        return route

    def validate_route(self, route: AgentRoute) -> None:
        """Validate agent names, task support, and role permissions."""
        if route.task_type not in SUPPORTED_TASK_TYPES:
            raise RouteValidationError(f"Unsupported task_type '{route.task_type}'.")
        if not route.agents:
            raise RouteValidationError("Route must contain at least one agent.")
        unknown_agents = [agent for agent in route.agents if agent not in SUPPORTED_AGENTS]
        if unknown_agents:
            raise RouteValidationError(f"Unsupported agent selection: {', '.join(unknown_agents)}.")

        allowed = ROLE_AGENT_PERMISSIONS[route.role]
        if route.task_type == "full_intelligence_report" and not route.selected_agents:
            allowed = set(SUPPORTED_AGENTS)
        unauthorized = [agent for agent in route.agents if agent not in allowed]
        if unauthorized:
            raise RouteValidationError(
                f"Role '{route.role.value}' cannot execute agent(s): {', '.join(unauthorized)}."
            )
        if route.task_type == "generate_model_driven_candidates" and route.agents[-1] == CANDIDATE_RANKING_AGENT:
            return
        if route.agents[-1] != MANDATORY_FINAL_AGENT:
            raise RouteValidationError("guardrail_agent must be the final route step.")

    def explain_route(self, route: AgentRoute) -> str:
        """Return a human-readable route explanation."""
        return route.explanation

    @staticmethod
    def _normalize_selected_agents(selected_agents: list[str] | None) -> list[str]:
        if not selected_agents:
            return []
        normalized: list[str] = []
        for agent in selected_agents:
            candidate = agent.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    @staticmethod
    def _with_mandatory_guardrail(agents: list[str]) -> list[str]:
        route = [agent for agent in agents if agent != MANDATORY_FINAL_AGENT]
        route.append(MANDATORY_FINAL_AGENT)
        return route

    @staticmethod
    def _filter_to_role_permissions(role: SupportedRole, agents: list[str]) -> list[str]:
        allowed = ROLE_AGENT_PERMISSIONS[role]
        return [agent for agent in agents if agent in allowed]

    @staticmethod
    def _build_explanation(role: SupportedRole, task_type: str, agents: list[str]) -> str:
        agent_list = " -> ".join(agents)
        return (
            f"Route selected for role '{role.value}' and task '{task_type}'. "
            f"Execution path: {agent_list}."
        )


def route_agents(role: SupportedRole, task_type: str, selected_agents: list[str] | None = None) -> list[str]:
    """Backward-compatible helper returning only agent names."""
    return RoleAwareRouter().route(role=role, task_type=task_type, query="", selected_agents=selected_agents).agents
