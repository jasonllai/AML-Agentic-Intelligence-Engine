"""Dynamic LangGraph assembly for routed AML agent execution."""

from collections.abc import Callable
from typing import Any

from app.agents.nodes import make_agent_nodes
from app.agents.router import AgentRoute
from app.agents.state import AMLAgentState

GraphRunner = Callable[[AMLAgentState], AMLAgentState]


class DynamicGraphBuilder:
    """Compile a sequential graph for exactly the selected agent route."""

    def __init__(self, node_registry: dict[str, Callable[[AMLAgentState], AMLAgentState]] | None = None) -> None:
        self.node_registry = node_registry or make_agent_nodes()

    def build(self, route: AgentRoute) -> Any:
        """Build a LangGraph workflow for the selected route.

        The graph contains only the selected route steps. This keeps execution
        modular and prevents non-required agents from reading state.
        """
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            return self._fallback_runner(route)

        graph = StateGraph(AMLAgentState)
        for agent_name in route.agents:
            graph.add_node(agent_name, self.node_registry[agent_name])

        graph.set_entry_point(route.agents[0])
        for current_agent, next_agent in zip(route.agents, route.agents[1:], strict=False):
            graph.add_edge(current_agent, next_agent)
        graph.add_edge(route.agents[-1], END)
        return graph.compile()

    def run(self, route: AgentRoute, state: AMLAgentState) -> AMLAgentState:
        """Execute a dynamically selected graph and return final state."""
        runner = self.build(route)
        if hasattr(runner, "invoke"):
            return AMLAgentState(runner.invoke(state))
        return runner(state)

    def _fallback_runner(self, route: AgentRoute) -> GraphRunner:
        """Return a local sequential runner if LangGraph is unavailable."""

        def run(state: AMLAgentState) -> AMLAgentState:
            current_state = state
            for agent_name in route.agents:
                current_state = self.node_registry[agent_name](current_state)
            return current_state

        return run


def build_graph(route: AgentRoute) -> Any:
    """Build a dynamic graph for a route."""
    return DynamicGraphBuilder().build(route)


def execute_graph(route: AgentRoute, state: AMLAgentState) -> AMLAgentState:
    """Execute a dynamic graph for a route."""
    return DynamicGraphBuilder().run(route, state)
