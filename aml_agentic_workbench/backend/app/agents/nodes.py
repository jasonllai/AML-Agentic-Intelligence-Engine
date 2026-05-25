"""LLM-backed AML agent nodes used by the dynamic LangGraph workflow."""

from typing import Any

from app.agents.router import (
    EVIDENCE_ASSEMBLY_AGENT,
    FEATURE_CRITIC_AGENT,
    GUARDRAIL_AGENT,
    JUDGE_PANEL_AGENT,
    MODEL_EXPLANATION_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import AMLAgentState
from app.evaluation.judge_panel import JudgePanel
from app.llm.client import LLMClient, get_llm_client
from app.llm.prompts import render_prompt
from app.llm.schemas import (
    EvidenceAssemblyOutput,
    FeatureCriticOutput,
    GuardrailReviewOutput,
    ModelExplanationOutput,
    TransactionBehaviourOutput,
    TypologyMappingOutput,
)
from app.services.data_service import DataService, get_data_service
from app.services.knowledge_retriever import KnowledgeRetriever, get_knowledge_retriever

AgentNode = Any


def make_agent_nodes(
    data_service: DataService | None = None,
    knowledge_retriever: KnowledgeRetriever | None = None,
    llm_client: LLMClient | None = None,
) -> dict[str, AgentNode]:
    """Create LLM-backed node callables keyed by supported agent name."""
    service = data_service or get_data_service()
    retriever = knowledge_retriever or get_knowledge_retriever()
    client = llm_client or get_llm_client()
    return {
        TRANSACTION_BEHAVIOUR_AGENT: transaction_behaviour_agent(service, client),
        MODEL_EXPLANATION_AGENT: model_explanation_agent(service, client),
        TYPOLOGY_MAPPING_AGENT: typology_mapping_agent(retriever, client),
        FEATURE_CRITIC_AGENT: feature_critic_agent(service, client),
        EVIDENCE_ASSEMBLY_AGENT: evidence_assembly_agent(client),
        JUDGE_PANEL_AGENT: judge_panel_agent(client),
        GUARDRAIL_AGENT: guardrail_agent(client),
    }


def transaction_behaviour_agent(data_service: DataService, llm_client: LLMClient) -> AgentNode:
    """Build a node that analyzes customer transaction behaviour."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        transactions = data_service.get_transactions(customer_id) if customer_id else []
        feature_summary = data_service.get_feature_summary(customer_id) if customer_id else {}
        network_summary = data_service.get_network_summary(customer_id) if customer_id else {}
        inputs = {
            "customer_feature_summary": feature_summary,
            "customer_transactions": transactions[:50],
            "network_summary": network_summary,
        }
        prompt = render_prompt(TRANSACTION_BEHAVIOUR_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, TransactionBehaviourOutput)
        state["transaction_summary"] = output.model_dump(mode="json")
        return _record_agent_output(
            state,
            TRANSACTION_BEHAVIOUR_AGENT,
            summary=output.behavioural_summary,
            findings=output.abnormal_patterns,
            evidence=[item.model_dump(mode="json") for item in output.evidence_items],
            limitations=[output.uncertainty],
            confidence=0.82 if transactions else 0.35,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def model_explanation_agent(data_service: DataService, llm_client: LLMClient) -> AgentNode:
    """Build a node that explains model outputs without treating scores as proof."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        outputs = data_service.get_model_outputs(customer_id) if customer_id else {}
        feature_summary = data_service.get_feature_summary(customer_id) if customer_id else {}
        inputs = {"model_outputs": outputs, "feature_summary": feature_summary}
        prompt = render_prompt(MODEL_EXPLANATION_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, ModelExplanationOutput)
        state["model_outputs"] = outputs
        return _record_agent_output(
            state,
            MODEL_EXPLANATION_AGENT,
            summary=output.model_summary,
            findings=[output.score_interpretation, *output.top_risk_drivers],
            evidence=[outputs] if outputs else [],
            limitations=[output.model_uncertainty, *output.caveats],
            confidence=0.78 if outputs else 0.3,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def typology_mapping_agent(knowledge_retriever: KnowledgeRetriever, llm_client: LLMClient) -> AgentNode:
    """Build a node that maps behaviour to AML typologies using careful language."""

    def node(state: AMLAgentState) -> AMLAgentState:
        documents = knowledge_retriever.search(state["query"], limit=3)
        serialized = [document.model_dump(mode="json") for document in documents]
        state["retrieved_documents"] = serialized
        inputs = {
            "behaviour_analysis": state.get("agent_outputs", {}).get(TRANSACTION_BEHAVIOUR_AGENT, {}),
            "retrieved_aml_knowledge_documents": serialized,
        }
        prompt = render_prompt(TYPOLOGY_MAPPING_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, TypologyMappingOutput)
        citations = [citation.model_dump(mode="json") for citation in output.citations]
        return _record_agent_output(
            state,
            TYPOLOGY_MAPPING_AGENT,
            summary=output.careful_language_summary,
            findings=[*output.matched_typologies, *output.supporting_indicators],
            evidence=serialized,
            limitations=output.missing_evidence,
            confidence=output.confidence,
            citations=citations,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def feature_critic_agent(data_service: DataService, llm_client: LLMClient) -> AgentNode:
    """Build a node that critiques AML feature quality and recommends PySpark features."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        features = data_service.get_feature_summary(customer_id) if customer_id else {}
        model_outputs = data_service.get_model_outputs(customer_id) if customer_id else {}
        inputs = {
            "feature_summary": features,
            "behaviour_analysis": state.get("agent_outputs", {}).get(TRANSACTION_BEHAVIOUR_AGENT, {}),
            "model_outputs": model_outputs,
        }
        prompt = render_prompt(FEATURE_CRITIC_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, FeatureCriticOutput)
        return _record_agent_output(
            state,
            FEATURE_CRITIC_AGENT,
            summary="Reviewed AML feature quality and generated validation-ready recommendations.",
            findings=output.feature_quality_findings,
            evidence=[features] if features else [],
            limitations=[*output.unstable_features, *output.possible_leakage_risks],
            confidence=0.74 if features else 0.3,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def evidence_assembly_agent(llm_client: LLMClient) -> AgentNode:
    """Build a node that assembles role/task-adapted final report sections."""

    def node(state: AMLAgentState) -> AMLAgentState:
        prior_outputs = state.get("agent_outputs", {})
        inputs = {
            "role": state["role"].value,
            "task_type": state["task_type"],
            "executed_agents": state.get("executed_agents", []),
            "agent_outputs": prior_outputs,
        }
        prompt = render_prompt(EVIDENCE_ASSEMBLY_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, EvidenceAssemblyOutput)
        report_markdown = _compose_adaptive_report(state, output)
        state["final_report"] = report_markdown
        return _record_agent_output(
            state,
            EVIDENCE_ASSEMBLY_AGENT,
            summary="Assembled a role-aware AML intelligence report from routed agent outputs.",
            findings=output.included_sections,
            evidence=output.evidence_table,
            limitations=output.limitations_and_uncertainty,
            confidence=0.8 if prior_outputs else 0.45,
            structured_output={**output.model_dump(mode="json"), "report_markdown": report_markdown},
        )

    return node


def judge_panel_agent(llm_client: LLMClient) -> AgentNode:
    """Build a node that scores the routed analysis output."""

    def node(state: AMLAgentState) -> AMLAgentState:
        output_text = state.get("final_report") or str(state.get("agent_outputs", {}))
        context = _evaluation_context(state)
        output = JudgePanel(llm_client=llm_client).evaluate(output_text, context)
        judge_outputs = {
            "overall_score": output.overall_score,
            "pass_fail": output.pass_fail,
            **{criterion.value: decision.score for criterion, decision in output.decisions.items()},
        }
        state["judge_outputs"] = judge_outputs
        return _record_agent_output(
            state,
            JUDGE_PANEL_AGENT,
            summary=output.failure_reason or "LLM-as-judge panel completed quality review.",
            findings=[
                f"{criterion.value}: {decision.pass_fail} ({decision.score})"
                for criterion, decision in output.decisions.items()
            ],
            evidence=[output.model_dump(mode="json")],
            limitations=["LLM-as-judge supports continuous feedback but does not replace sensitive action approvals."],
            confidence=output.overall_score,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def guardrail_agent(llm_client: LLMClient) -> AgentNode:
    """Build a node that performs final compliance guardrail review."""

    def node(state: AMLAgentState) -> AMLAgentState:
        inputs = {
            "final_report": state.get("final_report"),
            "agent_outputs": state.get("agent_outputs", {}),
            "judge_outputs": state.get("judge_outputs", {}),
        }
        prompt = render_prompt(GUARDRAIL_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, GuardrailReviewOutput)
        flags = list(output.flags)
        if not state.get("query", "").strip():
            flags.append("empty_query")
        if not state.get("agent_outputs"):
            flags.append("no_agent_outputs")
        state["guardrail_flags"] = flags
        if not state.get("final_report"):
            state["final_report"] = _compose_fallback_final_report(state, flags)
        return _record_agent_output(
            state,
            GUARDRAIL_AGENT,
            summary=output.safe_summary,
            findings=["No blocking guardrail flags found."] if not flags else flags,
            evidence=[{"flags": flags, "route": state.get("route", [])}],
            limitations=output.required_disclaimers,
            confidence=0.86 if not flags else 0.55,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def _record_agent_output(
    state: AMLAgentState,
    agent_name: str,
    *,
    summary: str,
    findings: list[str],
    evidence: list[dict[str, Any]],
    limitations: list[str],
    confidence: float,
    citations: list[dict[str, Any]] | None = None,
    structured_output: dict[str, Any] | None = None,
) -> AMLAgentState:
    output = {
        "summary": summary,
        "findings": findings,
        "evidence": evidence,
        "limitations": limitations,
        "confidence": round(confidence, 2),
        "citations": citations or [],
        "structured_output": structured_output or {},
    }
    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs[agent_name] = output
    state["agent_outputs"] = agent_outputs
    state["executed_agents"] = [*state.get("executed_agents", []), agent_name]
    state["audit_trace"] = [
        *state.get("audit_trace", []),
        {"event": "agent_completed", "agent": agent_name, "confidence": output["confidence"]},
    ]
    return state


def _compose_fallback_final_report(state: AMLAgentState, flags: list[str]) -> str:
    route = " -> ".join(state.get("route", []))
    sections = [
        "# AML Intelligence Report",
        "## Executive Summary",
        f"Role: {state['role'].value}. Task: {state['task_type']}.",
        f"Route: {route}",
        f"Guardrail status: {'flagged' if flags else 'passed'}",
        "## Limitations and Uncertainty",
        "This report was generated from routed agent outputs and synthetic sample data.",
    ]
    for agent, output in state.get("agent_outputs", {}).items():
        if agent != GUARDRAIL_AGENT:
            sections.extend([f"## {agent}", str(output.get("summary"))])
    return "\n\n".join(sections)


def _compose_adaptive_report(state: AMLAgentState, output: EvidenceAssemblyOutput) -> str:
    """Compose the governed report with only sections supported by executed agents."""
    agent_outputs = state.get("agent_outputs", {})
    sections = [
        "# AML Intelligence Report",
        "## Executive Summary",
        f"Role `{state['role'].value}` requested `{state['task_type']}`. {output.report_markdown.splitlines()[0]}",
    ]
    if TRANSACTION_BEHAVIOUR_AGENT in agent_outputs:
        sections.extend(
            [
                "## Customer Behaviour Overview",
                str(agent_outputs[TRANSACTION_BEHAVIOUR_AGENT].get("summary", "")),
            ]
        )
    if MODEL_EXPLANATION_AGENT in agent_outputs:
        sections.extend(
            [
                "## Model Risk Explanation",
                str(agent_outputs[MODEL_EXPLANATION_AGENT].get("summary", "")),
            ]
        )
    if TYPOLOGY_MAPPING_AGENT in agent_outputs:
        sections.extend(
            [
                "## Typology Mapping",
                str(agent_outputs[TYPOLOGY_MAPPING_AGENT].get("summary", "")),
            ]
        )
    if FEATURE_CRITIC_AGENT in agent_outputs:
        sections.extend(
            [
                "## Feature Quality Review",
                str(agent_outputs[FEATURE_CRITIC_AGENT].get("summary", "")),
            ]
        )

    evidence_rows = []
    for agent_name, agent_output in agent_outputs.items():
        evidence_rows.append(
            f"| {agent_name} | {agent_output.get('summary', '')} | {agent_output.get('confidence', '')} |"
        )
    sections.extend(
        [
            "## Evidence Table",
            "| Agent | Evidence Summary | Confidence |",
            "| --- | --- | --- |",
            *evidence_rows,
            "## Limitations and Uncertainty",
            *[f"- {item}" for item in output.limitations_and_uncertainty],
            "## Recommended Analytical Next Steps",
            *[f"- {item}" for item in output.recommended_next_steps],
        ]
    )
    return "\n".join(sections)


def _evaluation_context(state: AMLAgentState) -> dict[str, Any]:
    """Collect evaluation context for judge and policy layers."""
    citations: list[dict[str, object]] = []
    for output in state.get("agent_outputs", {}).values():
        citations.extend(output.get("citations", []))
    return {
        "transactions": state.get("transaction_summary"),
        "model_outputs": state.get("model_outputs"),
        "documents": state.get("retrieved_documents", []),
        "citations": citations,
        "agent_outputs": state.get("agent_outputs", {}),
    }
