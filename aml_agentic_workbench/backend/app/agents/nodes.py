"""LLM-backed AML agent nodes used by the dynamic LangGraph workflow."""

from typing import Any

from app.agents.router import (
    CANDIDATE_RANKING_AGENT,
    CASE_INVESTIGATION_AGENT,
    EVIDENCE_ASSEMBLY_AGENT,
    FEATURE_CRITIC_AGENT,
    GUARDRAIL_AGENT,
    JUDGE_PANEL_AGENT,
    MODEL_EXPLANATION_AGENT,
    REPORT_CRITIC_AGENT,
    SUPERVISOR_PLANNER_AGENT,
    TRANSACTION_BEHAVIOUR_AGENT,
    TYPOLOGY_MAPPING_AGENT,
)
from app.agents.state import AMLAgentState
from app.evaluation.judge_panel import JudgePanel
from app.llm.client import LLMClient, get_llm_client
from app.llm.prompts import render_prompt
from app.llm.schemas import (
    CriticReviewOutput,
    EvidenceAssemblyOutput,
    FeatureCriticOutput,
    GuardrailReviewOutput,
    ModelExplanationOutput,
    PlannerDecisionOutput,
    TransactionBehaviourOutput,
    TypologyMappingOutput,
)
from app.ml.model_service import ModelArtifactError, ModelService, get_model_service
from app.rag.pgvector_store import RagStoreUnavailable
from app.services.candidate_service import CandidateGenerationService
from app.services.data_service import DataService, get_data_service
from app.services.knowledge_retriever import KnowledgeRetriever, LocalKeywordRetriever, get_knowledge_retriever

AgentNode = Any


def make_agent_nodes(
    data_service: DataService | None = None,
    knowledge_retriever: KnowledgeRetriever | None = None,
    llm_client: LLMClient | None = None,
    model_service: ModelService | None = None,
) -> dict[str, AgentNode]:
    """Create LLM-backed node callables keyed by supported agent name."""
    service = data_service or get_data_service()
    retriever = knowledge_retriever or get_knowledge_retriever()
    client = llm_client or get_llm_client()
    scorer = model_service or get_model_service()
    return {
        TRANSACTION_BEHAVIOUR_AGENT: transaction_behaviour_agent(service, client),
        MODEL_EXPLANATION_AGENT: model_explanation_agent(service, client, scorer),
        TYPOLOGY_MAPPING_AGENT: typology_mapping_agent(retriever, client),
        FEATURE_CRITIC_AGENT: feature_critic_agent(service, client, scorer),
        CANDIDATE_RANKING_AGENT: candidate_ranking_agent(service, scorer, client),
        CASE_INVESTIGATION_AGENT: case_investigation_agent(service, scorer),
        SUPERVISOR_PLANNER_AGENT: supervisor_planner_agent(client),
        EVIDENCE_ASSEMBLY_AGENT: evidence_assembly_agent(client),
        REPORT_CRITIC_AGENT: report_critic_agent(client),
        JUDGE_PANEL_AGENT: judge_panel_agent(client),
        GUARDRAIL_AGENT: guardrail_agent(client),
    }


def transaction_behaviour_agent(data_service: DataService, llm_client: LLMClient) -> AgentNode:
    """Build a node that analyzes customer transaction behaviour."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        transactions = _safe_transactions(data_service, customer_id)
        feature_summary = _safe_feature_summary(data_service, customer_id)
        network_summary = _safe_network_summary(data_service, customer_id)
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


def model_explanation_agent(
    data_service: DataService,
    llm_client: LLMClient,
    model_service: ModelService | None = None,
) -> AgentNode:
    """Build a node that explains model outputs without treating scores as proof."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        outputs = _score_or_untrained(model_service, customer_id)
        feature_summary = _safe_feature_summary(data_service, customer_id)
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
        fallback_reason = ""
        try:
            documents = knowledge_retriever.search(state["query"], limit=3)
        except RagStoreUnavailable:
            if state["task_type"] != "investigate_model_prioritized_candidate":
                raise
            fallback_reason = (
                "pgvector unavailable; used local keyword fallback for primary investigator handoff review."
            )
            documents = LocalKeywordRetriever().search(state["query"], limit=3)
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
            limitations=([fallback_reason] if fallback_reason else []) + output.missing_evidence,
            confidence=output.confidence,
            citations=citations,
            structured_output=output.model_dump(mode="json"),
        )

    return node


def feature_critic_agent(
    data_service: DataService,
    llm_client: LLMClient,
    model_service: ModelService | None = None,
) -> AgentNode:
    """Build a node that critiques AML feature quality and recommends PySpark features."""

    def node(state: AMLAgentState) -> AMLAgentState:
        customer_id = state.get("customer_id")
        features = _safe_feature_summary(data_service, customer_id)
        model_outputs = _score_or_untrained(model_service, customer_id)
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


def candidate_ranking_agent(
    data_service: DataService,
    model_service: ModelService | None = None,
    llm_client: LLMClient | None = None,
) -> AgentNode:
    """Build a node that creates ranked model-driven candidates for investigator handoff."""

    def node(state: AMLAgentState) -> AMLAgentState:
        result = CandidateGenerationService(
            data_service=data_service,
            model_service=model_service,
            llm_client=llm_client,
        ).generate(top_k=10)
        state["candidate_packages"] = result["candidate_packages"]
        state["model_run_summary"] = result["model_run_summary"]
        state["model_results"] = result.get("model_results", {})
        state["model_outputs"] = result
        findings = [
            f"Rank {package['rank']}: {package['customer_id']} score {package['score']}"
            for package in result["candidate_packages"][:5]
        ]
        return _record_agent_output(
            state,
            CANDIDATE_RANKING_AGENT,
            summary="Generated model-driven AML investigation candidates for investigator handoff.",
            findings=findings or ["No model candidates generated; model artifact may be unavailable."],
            evidence=result["candidate_packages"],
            limitations=result["model_limitations"],
            confidence=0.8 if result["candidate_packages"] else 0.35,
            structured_output=result,
        )

    return node


def case_investigation_agent(data_service: DataService, model_service: ModelService | None = None) -> AgentNode:
    """Build a node that prepares investigator case review and feedback."""

    def node(state: AMLAgentState) -> AMLAgentState:
        review = CandidateGenerationService(
            data_service=data_service,
            model_service=model_service,
        ).build_case_review(
            state.get("customer_id"),
            query=state["query"],
            state_outputs=state.get("agent_outputs", {}),
        )
        state["investigation_case_review"] = review
        return _record_agent_output(
            state,
            CASE_INVESTIGATION_AGENT,
            summary="Prepared investigator case review and feedback for model monitoring.",
            findings=[
                f"Disposition recommendation: {review['disposition_recommendation']}",
                f"Model feedback label: {review['investigator_feedback']['label_for_model_evaluation']}",
            ],
            evidence=[review["candidate_package"]],
            limitations=review["missing_evidence"],
            confidence=0.76,
            structured_output=review,
        )

    return node


def supervisor_planner_agent(llm_client: LLMClient) -> AgentNode:
    """Build a node that proposes the next bounded investigator evidence action."""

    def node(state: AMLAgentState) -> AMLAgentState:
        completed_agents = [
            agent
            for agent in state.get("executed_agents", [])
            if agent in {TRANSACTION_BEHAVIOUR_AGENT, TYPOLOGY_MAPPING_AGENT, CASE_INVESTIGATION_AGENT}
        ]
        inputs = {
            "allowed_actions": [
                TRANSACTION_BEHAVIOUR_AGENT,
                TYPOLOGY_MAPPING_AGENT,
                CASE_INVESTIGATION_AGENT,
                "finalize_report",
            ],
            "completed_agents": completed_agents,
            "agent_outputs": {
                agent: state.get("agent_outputs", {}).get(agent, {}) for agent in completed_agents
            },
            "planner_decisions_so_far": state.get("planner_decisions", []),
        }
        prompt = render_prompt(SUPERVISOR_PLANNER_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, PlannerDecisionOutput)
        decision = output.model_dump(mode="json")
        state["planner_decisions"] = [*state.get("planner_decisions", []), decision]
        if output.stop_reason:
            state["stop_reason"] = output.stop_reason
        state["audit_trace"] = [
            *state.get("audit_trace", []),
            {
                "event": "planner_decision",
                "agent": SUPERVISOR_PLANNER_AGENT,
                "next_action": output.next_action,
                "confidence": round(output.confidence, 2),
            },
        ]
        return state

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
            "critic_reviews": state.get("critic_reviews", []),
            "refinement_rounds": state.get("refinement_rounds", 0),
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


def report_critic_agent(llm_client: LLMClient) -> AgentNode:
    """Build a node that critiques the draft report before final governance."""

    def node(state: AMLAgentState) -> AMLAgentState:
        inputs = {
            "final_report": state.get("final_report"),
            "agent_outputs": state.get("agent_outputs", {}),
            "planner_decisions": state.get("planner_decisions", []),
            "refinement_rounds": state.get("refinement_rounds", 0),
        }
        prompt = render_prompt(REPORT_CRITIC_AGENT, state["role"], state["query"], inputs)
        output = llm_client.generate_structured(prompt, CriticReviewOutput)
        review = output.model_dump(mode="json")
        state["critic_reviews"] = [*state.get("critic_reviews", []), review]
        return _record_agent_output(
            state,
            REPORT_CRITIC_AGENT,
            summary=f"Critic review completed with status: {output.status}.",
            findings=output.issues or ["No material refinement issue found."],
            evidence=[
                {
                    "target_section": output.target_section,
                    "refinement_instruction": output.refinement_instruction,
                    "must_refine": output.must_refine,
                }
            ],
            limitations=["Critic refinement is bounded to one pass before final governance."],
            confidence=output.confidence,
            structured_output=review,
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
        "This report was generated from routed agent outputs and available real-data evidence.",
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
        f"Requested focus: {state['query']}",
    ]
    if TRANSACTION_BEHAVIOUR_AGENT in agent_outputs:
        sections.extend(
            [
                "## Customer Behaviour Overview",
                str(agent_outputs[TRANSACTION_BEHAVIOUR_AGENT].get("summary", "")),
            ]
        )
    if CANDIDATE_RANKING_AGENT in agent_outputs:
        packages = state.get("candidate_packages", [])
        ranking_rows = [
            f"| {package['rank']} | {package['customer_id']} | {package['score']} | {package['alert_recommendation']} |"
            for package in packages[:10]
        ]
        sections.extend(
            [
                "## Model-Driven Candidate Ranking",
                str(agent_outputs[CANDIDATE_RANKING_AGENT].get("summary", "")),
                "| Rank | Customer | Score | Recommendation |",
                "| --- | --- | --- | --- |",
                *ranking_rows,
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
    if CASE_INVESTIGATION_AGENT in agent_outputs:
        review = state.get("investigation_case_review", {})
        feedback = review.get("investigator_feedback", {}) if isinstance(review, dict) else {}
        sections.extend(
            [
                "## Investigator Case Review",
                str(agent_outputs[CASE_INVESTIGATION_AGENT].get("summary", "")),
                f"Disposition recommendation: {review.get('disposition_recommendation', 'unknown')}",
                f"Model feedback label: {feedback.get('label_for_model_evaluation', 'unknown')}",
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


def _untrained_model_output(customer_id: str | None) -> dict[str, Any]:
    """Return an explicit no-artifact model state instead of assuming precomputed scores."""
    return {
        "customer_id": customer_id,
        "model_version": "untrained",
        "risk_score": None,
        "anomaly_score": None,
        "reconstruction_error": None,
        "alert_recommendation": "model_artifact_required",
        "top_features": [],
        "explanation_metadata": {
            "backend": "none",
            "status": "No trained model artifact was loaded. Run python -m app.ml.train_model first.",
        },
    }


def _safe_feature_summary(data_service: DataService, customer_id: str | None) -> dict[str, Any]:
    if not customer_id:
        return {}
    try:
        return data_service.get_feature_summary(customer_id)
    except ValueError as exc:
        return {"customer_id": customer_id, "status": "feature_summary_unavailable", "reason": str(exc)}


def _safe_transactions(data_service: DataService, customer_id: str | None) -> list[dict[str, Any]]:
    if not customer_id:
        return []
    try:
        return data_service.get_transactions(customer_id)
    except ValueError:
        return []


def _safe_network_summary(data_service: DataService, customer_id: str | None) -> dict[str, Any]:
    if not customer_id:
        return {}
    try:
        return data_service.get_network_summary(customer_id)
    except ValueError as exc:
        return {"customer_id": customer_id, "status": "network_summary_unavailable", "reason": str(exc)}


def _score_or_untrained(model_service: ModelService | None, customer_id: str | None) -> dict[str, Any]:
    if customer_id and model_service:
        try:
            return model_service.score_customer(customer_id)
        except ModelArtifactError:
            return _untrained_model_output(customer_id)
    return _untrained_model_output(customer_id)
