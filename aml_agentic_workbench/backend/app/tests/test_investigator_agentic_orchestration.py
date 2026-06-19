"""Investigator supervisor planner and critic loop tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agents.investigator_orchestrator import InvestigatorAgenticRunner
from app.agents.nodes import _record_agent_output, make_agent_nodes
from app.agents.router import (
    CASE_INVESTIGATION_AGENT,
    EVIDENCE_ASSEMBLY_AGENT,
    GUARDRAIL_AGENT,
    AgentRoute,
    JUDGE_PANEL_AGENT,
    REPORT_CRITIC_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import initial_state
from app.api.routes.analysis import _build_analysis_response
from app.guardrails.policy_engine import PolicyEngine
from app.llm.mock_client import MockLLMClient
from app.main import create_app
from app.schemas.analysis import AnalysisRequest
from app.schemas.knowledge import ScoredKnowledgeDocument
from app.schemas.roles import SupportedRole

REAL_CUSTOMER_ID = "SYNID0100000167"
UNSAFE_GOVERNANCE_REPORT = """# AML Intelligence Report

## Executive Summary
This customer is laundering money. Criminal activity confirmed.

## Recommended Analytical Next Steps
File an STR."""
SAFE_GOVERNANCE_REPORT = """# AML Intelligence Report

## Executive Summary
The behaviour resembles indicators associated with AML risk and may warrant further review. Model score is not proof
of suspicious activity. Evidence is insufficient to conclude suspicious or criminal activity; this requires human
review before action.

## Evidence Table
| Agent | Evidence Summary | Confidence |
| --- | --- | --- |
| transaction_behaviour_agent | Reviewed transaction behaviour evidence. | 0.82 |
| typology_mapping_agent | Compared behaviour to cited AML indicator context. | 0.72 |

## Limitations and Uncertainty
- Available evidence supports review prioritization, not a final disposition.

## Recommended Analytical Next Steps
- Review supporting transactions and customer context before any action."""
JUDGE_WARNING_REPORT = "Brief analyst note."


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


def test_guardrail_failure_triggers_one_remediation_and_can_fix_report() -> None:
    """Fixable final governance failures should route through critic and evidence assembly once."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())
    nodes[EVIDENCE_ASSEMBLY_AGENT] = _scripted_evidence_assembly(
        [UNSAFE_GOVERNANCE_REPORT, SAFE_GOVERNANCE_REPORT]
    )

    runner = InvestigatorAgenticRunner(node_registry=nodes, max_refinement_rounds=0)
    events = list(runner.run(state))
    final_state = runner.state
    event_names = [event["event"] for event in events]

    assert event_names.count("guardrail_remediation_started") == 1
    assert event_names.count("guardrail_remediation_completed") == 1
    assert final_state["guardrail_remediation_rounds"] == 1
    assert final_state["guardrail_flags"] == []
    assert final_state["executed_agents"].count(GUARDRAIL_AGENT) == 2
    assert final_state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]
    assert "criminal activity confirmed" not in final_state["final_report"].lower()


def test_guardrail_remediation_does_not_loop_after_repeated_failure() -> None:
    """Repeated governance failures should stop after one remediation and return a guarded failure."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())
    nodes[EVIDENCE_ASSEMBLY_AGENT] = _scripted_evidence_assembly([UNSAFE_GOVERNANCE_REPORT])

    runner = InvestigatorAgenticRunner(node_registry=nodes, max_refinement_rounds=0)
    events = list(runner.run(state))

    response = _build_analysis_response(
        request=AnalysisRequest(
            role=SupportedRole.INVESTIGATOR,
            task_type="investigate_model_prioritized_candidate",
            customer_id=REAL_CUSTOMER_ID,
            query="Investigate this model-prioritized candidate and return typology feedback.",
            require_full_report=False,
        ),
        run_id="test-remediation-failure",
        route=AgentRoute(
            role=SupportedRole.INVESTIGATOR,
            task_type="investigate_model_prioritized_candidate",
            query="Investigate this model-prioritized candidate and return typology feedback.",
            agents=runner.state["route"],
            explanation="test route",
        ),
        final_state=runner.state,
        policy_engine=PolicyEngine(),
    )

    event_names = [event["event"] for event in events]
    assert event_names.count("guardrail_remediation_started") == 1
    assert runner.state["guardrail_remediation_rounds"] == 1
    assert runner.state["executed_agents"].count(GUARDRAIL_AGENT) == 2
    assert runner.state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]
    assert response.status == "guardrail_failed"
    assert response.guardrail_status == "failed"
    assert response.result["governance_status"] == "guardrail_failed"
    assert response.result["guardrail_failure_reasons"]
    assert "judge_panel_failed" not in response.result["guardrail_failure_reasons"]
    assert response.result["judge_failure_reasons"]
    assert response.result["guardrail_remediation_rounds"] == 1


def test_judge_only_failure_returns_warning_not_guardrail_failure() -> None:
    """A weak report without guardrail flags should be a judge warning, not a guardrail failure."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    state["route"] = [EVIDENCE_ASSEMBLY_AGENT, JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]
    state["executed_agents"] = [EVIDENCE_ASSEMBLY_AGENT, JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]
    state["final_report"] = JUDGE_WARNING_REPORT
    state["agent_outputs"] = {
        EVIDENCE_ASSEMBLY_AGENT: {
            "summary": "Short report assembled.",
            "findings": [],
            "evidence": [],
            "limitations": [],
            "confidence": 0.4,
            "citations": [],
            "structured_output": {},
        }
    }
    state["guardrail_flags"] = []

    response = _build_analysis_response(
        request=AnalysisRequest(
            role=SupportedRole.INVESTIGATOR,
            task_type="investigate_model_prioritized_candidate",
            customer_id=REAL_CUSTOMER_ID,
            query="Investigate this model-prioritized candidate and return typology feedback.",
            require_full_report=False,
        ),
        run_id="test-judge-warning",
        route=AgentRoute(
            role=SupportedRole.INVESTIGATOR,
            task_type="investigate_model_prioritized_candidate",
            query="Investigate this model-prioritized candidate and return typology feedback.",
            agents=state["route"],
            explanation="test route",
        ),
        final_state=state,
        policy_engine=PolicyEngine(),
    )

    assert response.status == "completed"
    assert response.guardrail_status == "passed"
    assert response.result["governance_status"] == "judge_warning"
    assert response.result["judge_status"] == "warning"
    assert response.result["final_report"] == JUDGE_WARNING_REPORT
    assert response.result["guardrail_failure_reasons"] == []
    assert response.result["judge_failure_reasons"]
    assert any(event["event"] == "judge_warning" for event in response.result["audit_trace"])
    assert all(event["event"] != "guardrail_failed" for event in response.result["audit_trace"])


def test_judge_only_failure_does_not_start_guardrail_remediation() -> None:
    """Guardrail remediation should be reserved for guardrail flags, not judge-only warnings."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())
    nodes[EVIDENCE_ASSEMBLY_AGENT] = _scripted_evidence_assembly([SAFE_GOVERNANCE_REPORT])
    nodes[JUDGE_PANEL_AGENT] = _judge_only_failure_node
    nodes[GUARDRAIL_AGENT] = _passing_guardrail_node

    runner = InvestigatorAgenticRunner(node_registry=nodes, max_refinement_rounds=0)
    events = list(runner.run(state))

    event_names = [event["event"] for event in events]
    assert "guardrail_remediation_started" not in event_names
    assert runner.state["guardrail_remediation_rounds"] == 0
    assert runner.state["guardrail_flags"] == []
    assert runner.state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]


def test_guardrail_report_quality_flags_trigger_remediation_loop() -> None:
    """Fixable report-quality guardrail flags should trigger one remediation pass before final failure."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())
    nodes[EVIDENCE_ASSEMBLY_AGENT] = _scripted_evidence_assembly(
        [SAFE_GOVERNANCE_REPORT, SAFE_GOVERNANCE_REPORT]
    )
    nodes[JUDGE_PANEL_AGENT] = _passing_judge_node
    nodes[GUARDRAIL_AGENT] = _scripted_guardrail_node(
        [
            [
                "premature_disposition: case closed as false positive despite unresolved data gaps",
                "unsupported_claim: disposition recommendation 'close' not fully justified",
                "disclaimer_needed: model output is prioritization only and not proof of suspicious activity",
            ],
            [],
        ]
    )

    runner = InvestigatorAgenticRunner(node_registry=nodes, max_refinement_rounds=0)
    events = list(runner.run(state))
    event_names = [event["event"] for event in events]

    assert event_names.count("guardrail_remediation_started") == 1
    assert event_names.count("guardrail_remediation_completed") == 1
    assert runner.state["guardrail_remediation_rounds"] == 1
    assert runner.state["guardrail_flags"] == []
    assert runner.state["executed_agents"].count(GUARDRAIL_AGENT) == 2
    assert runner.state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]


def test_guardrail_disposition_flags_trigger_remediation_loop() -> None:
    """Disposition/rationale guardrail flags from final review should trigger remediation."""
    state = initial_state(
        role=SupportedRole.INVESTIGATOR,
        task_type="investigate_model_prioritized_candidate",
        query="Investigate this model-prioritized candidate and return typology feedback.",
        customer_id=REAL_CUSTOMER_ID,
    )
    nodes = make_agent_nodes(knowledge_retriever=FakeKnowledgeRetriever(), llm_client=MockLLMClient())
    nodes[EVIDENCE_ASSEMBLY_AGENT] = _scripted_evidence_assembly(
        [SAFE_GOVERNANCE_REPORT, SAFE_GOVERNANCE_REPORT]
    )
    nodes[JUDGE_PANEL_AGENT] = _passing_judge_node
    nodes[GUARDRAIL_AGENT] = _scripted_guardrail_node(
        [
            [
                "contradictory_disposition",
                "unsupported_false_positive_rationale",
                "definitive_conclusion_without_resolving_red_flags",
            ],
            [],
        ]
    )

    runner = InvestigatorAgenticRunner(node_registry=nodes, max_refinement_rounds=0)
    events = list(runner.run(state))
    event_names = [event["event"] for event in events]

    assert event_names.count("guardrail_remediation_started") == 1
    assert event_names.count("guardrail_remediation_completed") == 1
    assert runner.state["guardrail_remediation_rounds"] == 1
    assert runner.state["guardrail_flags"] == []
    assert runner.state["executed_agents"].count(GUARDRAIL_AGENT) == 2
    assert runner.state["executed_agents"][-2:] == [JUDGE_PANEL_AGENT, GUARDRAIL_AGENT]


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
    assert result["guardrail_remediation_rounds"] == 0
    assert result["governance_status"] in {"passed", "judge_warning", "guardrail_failed"}
    assert result["judge_status"] in {"passed", "warning"}
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


def _scripted_evidence_assembly(reports: list[str]):
    calls = {"count": 0}

    def node(state):
        report = reports[min(calls["count"], len(reports) - 1)]
        calls["count"] += 1
        state["final_report"] = report
        return _record_agent_output(
            state,
            EVIDENCE_ASSEMBLY_AGENT,
            summary=f"Scripted evidence assembly draft {calls['count']}.",
            findings=["Draft report assembled from existing evidence."],
            evidence=[{"draft": calls["count"]}],
            limitations=["Test double for governance remediation."],
            confidence=0.8,
            structured_output={"report_markdown": report},
        )

    return node


def _judge_only_failure_node(state):
    state["judge_outputs"] = {
        "overall_score": 0.66,
        "pass_fail": "fail",
        "compliance": 0.2,
    }
    state["judge_panel_result"] = {
        "overall_score": 0.66,
        "pass_fail": "fail",
        "failure_reason": "Compliance judge failed with high severity.",
        "decisions": {
            "compliance": {
                "criterion": "compliance",
                "score": 0.2,
                "pass_fail": "fail",
                "explanation": "Test judge failure.",
                "detected_issues": ["Judge-only compliance issue."],
                "recommended_fix": "Review report quality.",
                "severity": "high",
            }
        },
    }
    return _record_agent_output(
        state,
        JUDGE_PANEL_AGENT,
        summary="Compliance judge failed with high severity.",
        findings=["compliance: fail (0.2)"],
        evidence=[state["judge_panel_result"]],
        limitations=["Test double for judge-only warning."],
        confidence=0.66,
        structured_output=state["judge_panel_result"],
    )


def _passing_guardrail_node(state):
    state["guardrail_flags"] = []
    state["guardrail_failure_reasons"] = []
    state["guardrail_allowed"] = True
    return _record_agent_output(
        state,
        GUARDRAIL_AGENT,
        summary="No blocking guardrail flags found.",
        findings=["No blocking guardrail flags found."],
        evidence=[{"flags": []}],
        limitations=[],
        confidence=0.86,
        structured_output={"flags": []},
    )


def _passing_judge_node(state):
    state["judge_outputs"] = {
        "overall_score": 0.9,
        "pass_fail": "pass",
        "compliance": 0.9,
    }
    state["judge_panel_result"] = {
        "overall_score": 0.9,
        "pass_fail": "pass",
        "failure_reason": None,
        "decisions": {
            "compliance": {
                "criterion": "compliance",
                "score": 0.9,
                "pass_fail": "pass",
                "explanation": "Test judge pass.",
                "detected_issues": [],
                "recommended_fix": None,
                "severity": "low",
            }
        },
    }
    return _record_agent_output(
        state,
        JUDGE_PANEL_AGENT,
        summary="LLM-as-judge panel completed quality review.",
        findings=["compliance: pass (0.9)"],
        evidence=[state["judge_panel_result"]],
        limitations=["Test double for judge pass."],
        confidence=0.9,
        structured_output=state["judge_panel_result"],
    )


def _scripted_guardrail_node(flag_rounds: list[list[str]]):
    calls = {"count": 0}

    def node(state):
        flags = flag_rounds[min(calls["count"], len(flag_rounds) - 1)]
        calls["count"] += 1
        state["guardrail_flags"] = flags
        state["guardrail_failure_reasons"] = flags
        state["guardrail_allowed"] = not flags
        return _record_agent_output(
            state,
            GUARDRAIL_AGENT,
            summary="No blocking guardrail flags found." if not flags else "Guardrail flags require remediation.",
            findings=["No blocking guardrail flags found."] if not flags else flags,
            evidence=[{"flags": flags, "failure_reasons": flags}],
            limitations=[],
            confidence=0.86 if not flags else 0.55,
            structured_output={"flags": flags},
        )

    return node
