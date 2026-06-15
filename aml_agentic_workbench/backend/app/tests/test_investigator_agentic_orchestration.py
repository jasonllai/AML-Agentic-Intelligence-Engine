"""Investigator supervisor planner and critic loop tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agents.investigator_orchestrator import InvestigatorAgenticRunner
from app.agents.nodes import make_agent_nodes
from app.agents.router import (
    CASE_INVESTIGATION_AGENT,
    GUARDRAIL_AGENT,
    JUDGE_PANEL_AGENT,
    REPORT_CRITIC_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import initial_state
from app.llm.mock_client import MockLLMClient
from app.main import create_app
from app.schemas.knowledge import ScoredKnowledgeDocument
from app.schemas.roles import SupportedRole

REAL_CUSTOMER_ID = "SYNID0100000167"


class FakeKnowledgeRetriever:
    """Knowledge retriever test double for investigator orchestration."""

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Return citation-ready typology context without requiring pgvector."""
        return [
            ScoredKnowledgeDocument(
                doc_id="fintrac:test",
                title="FINTRAC ML/TF indicators",
                source="FINTRAC - guidance",
                section="Indicators",
                text="FINTRAC indicators are red flags that require customer-context assessment.",
                url="https://fintrac-canafe.canada.ca/guidance-directives/transaction-operation/indicators-indicateurs/fin_mltf-eng",
                metadata={"organization": "FINTRAC"},
                score=0.9,
            )
        ][:limit]


def test_investigator_runner_plans_evidence_then_critic_then_final_governance() -> None:
    """Primary investigator runs should let the planner gather evidence before fixed governance."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())

    runner = InvestigatorAgenticRunner(node_registry=nodes)
    events = list(runner.run(state))
    final_state = runner.state

    decisions = final_state["planner_decisions"]
    assert [decision["next_action"] for decision in decisions[:4]] == [
        TRANSACTION_BEHAVIOUR_AGENT,
        TYPOLOGY_MAPPING_AGENT,
        CASE_INVESTIGATION_AGENT,
        "finalize_report",
    ]
    assert final_state["stop_reason"]
    assert final_state["critic_reviews"][0]["status"] in {"needs_refinement", "approved"}
    assert final_state["refinement_rounds"] <= 1
    assert REPORT_CRITIC_AGENT in final_state["executed_agents"]
    assert final_state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]
    assert [event["event"] for event in events].index("critic_completed") < [
        event["event"] for event in events
    ].index("judge_started")


def test_investigator_runner_streams_agent_outputs_before_final_completion() -> None:
    """Live monitoring needs planner decisions and agent output snippets before the final response."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())

    events = list(InvestigatorAgenticRunner(node_registry=nodes).run(state))

    event_names = [event["event"] for event in events]
    assert event_names[:2] == ["run_started", "planner_decision"]
    assert "agent_completed" in event_names
    assert "critic_completed" in event_names
    assert "refinement_completed" in event_names
    assert event_names[-2:] == ["guardrail_started", "agent_completed"]
    completed_transaction = next(
        event
        for event in events
        if event["event"] == "agent_completed" and event.get("agent") == TRANSACTION_BEHAVIOUR_AGENT
    )
    assert completed_transaction["output"]["summary"]
    assert completed_transaction["output"]["findings"]


def test_analysis_stream_endpoint_emits_ordered_investigator_events_and_final_payload() -> None:
    """The stream API should expose planner, critic, governance, and final response metadata."""
    client = TestClient(create_app())

    with client.stream(
        "POST",
        "/api/v1/analysis/stream",
        json={
            "role": "investigator",
            "task_type": "investigate_model_prioritized_candidate",
            "customer_id": REAL_CUSTOMER_ID,
            "query": "Investigate this model-prioritized candidate and return typology feedback.",
            "require_full_report": False,
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    events = _parse_sse(body)
    event_names = [event["event"] for event in events]
    assert "planner_decision" in event_names
    assert "critic_completed" in event_names
    assert event_names.index("judge_started") < event_names.index("guardrail_started")
    assert event_names.index("guardrail_started") < event_names.index("run_completed")
    final_event = events[-1]
    assert final_event["event"] == "run_completed"
    result = final_event["response"]["result"]
    assert result["planner_decisions"]
    assert result["critic_reviews"]
    assert result["stop_reason"]
    assert result["refinement_rounds"] <= 1
    assert final_event["response"]["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]


def test_analysis_stream_endpoint_rejects_customer_absent_from_real_data() -> None:
    """The UI streaming path must not generate reports for unknown real-data customers."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/stream",
        json={
            "role": "investigator",
            "task_type": "investigate_model_prioritized_candidate",
            "customer_id": "CUST003",
            "query": "Investigate this model-prioritized candidate.",
        },
    )

    assert response.status_code == 404
    assert "not found in real customer data" in response.json()["detail"]


def _parse_sse(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        event_name = next(line.removeprefix("event: ").strip() for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ").strip() for line in lines if line.startswith("data: "))
        payload = json.loads(data)
        payload["event"] = event_name
        events.append(payload)
    return events
