"""Agent run logging helpers for orchestration records."""

from datetime import UTC, datetime

from app.agents.state import AMLAgentState
from app.core.logging import get_logger
from app.storage.models import AgentRun, AgentStep

logger = get_logger(__name__)


class AgentRunLogger:
    """Create ORM run/step records and emit structured logs.

    This keeps API orchestration decoupled from database availability in the
    prototype while preserving the exact objects that will be persisted by a
    repository or unit-of-work in the next backend slice.
    """

    def create_run_record(
        self,
        *,
        run_id: str,
        role: str,
        task_type: str,
        query: str,
        customer_id: str | None,
        alert_id: str | None,
        route: list[str],
        route_explanation: str,
    ) -> AgentRun:
        """Create and log an AgentRun record."""
        run = AgentRun(
            id=run_id,
            role=role,
            task_type=task_type,
            status="completed",
            query=query,
            customer_id=customer_id,
            alert_id=alert_id,
            metadata_json={"route": route, "route_explanation": route_explanation},
        )
        logger.info(
            "agent_run_recorded",
            extra={"run_id": run_id, "role": role, "task_type": task_type, "route": route},
        )
        return run

    def create_step_records(self, run_id: str, state: AMLAgentState) -> list[AgentStep]:
        """Create and log AgentStep records from final graph state."""
        now = datetime.now(UTC)
        steps: list[AgentStep] = []
        agent_outputs = state.get("agent_outputs", {})
        for agent_name in state.get("executed_agents", []):
            output = agent_outputs.get(agent_name, {})
            step = AgentStep(
                run_id=run_id,
                agent_name=agent_name,
                status="completed",
                input_json={"route": state.get("route", []), "query": state.get("query")},
                output_json=output,
                started_at=now,
                completed_at=now,
            )
            steps.append(step)
            logger.info(
                "agent_step_recorded",
                extra={"run_id": run_id, "agent_name": agent_name, "status": "completed"},
            )
        return steps

