# AML Agentic Intelligence Workbench - System Overview

## Executive Summary

The AML Agentic Intelligence Workbench is a governed, role-aware multi-agent application for anti-money laundering analytics. It is designed to help bank teams convert structured AML data, model outputs, retrieved policy or typology context, and agent reasoning into controlled AML intelligence packages.

The current implementation is a production-oriented foundation rather than a complete enterprise deployment. It includes a FastAPI backend, a Next.js frontend, dynamic LangGraph-compatible agent routing, deterministic local sample data, real-data feature/model artifacts, mock-or-real LLM client abstraction, internal tool abstractions, guardrails, LLM-as-judge evaluation, pgvector-backed RAG retrieval, ORM persistence models, Docker Compose infrastructure for PostgreSQL and Redis, and tests. The local default path uses a deterministic mock LLM unless an OpenAI-compatible API key is configured.

## Business Purpose

AML teams often operate across disconnected artifacts: transaction monitoring alerts, engineered feature tables, model scores, typology playbooks, analyst notes, validation evidence, and governance requirements. This workbench provides a controlled way to assemble those inputs into explainable, role-specific outputs.

The business purpose is to support:

- Better explanation of customer behaviour and transaction patterns.
- Safer interpretation of AML model outputs without treating model scores as proof.
- Mapping of observed activity to AML typology indicators with careful, non-conclusive language.
- Identification of feature quality issues, leakage risks, and candidate feature improvements.
- Role-specific report packaging for investigators, data scientists, model validators, and compliance strategy users.
- Repeatable quality review through judge scores, deterministic guardrails, audit traces, and route explanations.

## Target Users

### Data Scientist

The data scientist user is interested in model behaviour, feature quality, signal stability, leakage risk, and possible new features. The workbench supports this user through the model explanation agent, feature critic agent, transaction behaviour context, judge scores, and structured feature recommendations with PySpark-style pseudocode.

Typical questions:

- Which features are driving the current AML risk signal?
- Does the model score have enough supporting behavioural context?
- Which features may be unstable or leakage-prone?
- What additional features could improve monitoring coverage?

### Investigator

The investigator user needs a concise, evidence-grounded view of customer activity. The workbench supports this user through transaction behaviour analysis, typology mapping, evidence assembly, careful wording, and visible guardrail status.

Typical questions:

- What recent customer behaviour appears unusual relative to baseline?
- Which counterparties, geographies, velocity changes, or transaction patterns matter?
- Which AML typology indicators does the activity resemble?
- What evidence should be reviewed before taking action?

### Model Validator

The model validator user needs auditability, uncertainty handling, validation caveats, and evidence that the system does not overstate model output. The workbench supports this user through model explanation, feature critique, judge scores, and report sections that emphasize model limitations.

Typical questions:

- Does the explanation clearly state that the model score is not proof?
- Are feature directionality, uncertainty, and data quality concerns surfaced?
- Are validation tests and stability checks identified?
- Is the output sufficiently traceable for governance review?

### Compliance or AML Strategy User

The compliance strategy user needs typology coverage, policy alignment, careful language, and governance visibility. The workbench supports this user through typology mapping, evidence assembly, citation requirements, policy guardrails, and approval-gate abstractions for sensitive actions.

Typical questions:

- Which typology indicators are covered by the available evidence?
- Does the output avoid legal conclusions and operationally unsafe instructions?
- Are citations present for regulatory or typology claims?
- Where are the policy and control gaps?

## Problems the System Solves

The current implementation addresses several common AML analytics problems:

- Fragmented evidence: The system assembles transactions, feature summaries, model outputs, retrieved knowledge, agent outputs, judge decisions, and guardrail status into one response package.
- Overbroad AI execution: The router selects only the agents needed for a role and task, with support for partial-agent execution and mandatory final guardrail review.
- Unsafe model interpretation: Structured schemas and judges require uncertainty language and prevent model scores from being framed as proof of suspicious activity.
- Unsupported typology claims: Typology outputs require citations at the schema level, and output guardrails flag typology language without citations.
- Inconsistent output quality: The judge panel evaluates faithfulness, citation support, compliance, typology wording, data science quality, and usefulness.
- Weak auditability: The system records route explanations, executed agents, agent completion events, judge scores, guardrail outcomes, and in-memory run history.
- Tool sprawl risk: Internal tools are registered through a typed, role-scoped, allowlisted registry rather than arbitrary code or shell execution.

## What the System Does Not Do

The codebase deliberately does not implement several enterprise capabilities yet:

- It does not make final AML decisions, confirm criminal activity, or direct users to file regulatory reports.
- It does not replace investigator judgment, model validation governance, or compliance approval workflows.
- It does not connect to live bank transaction systems, customer master data, case management platforms, or sanctions systems.
- It does not currently persist API analysis results to PostgreSQL in the request path. ORM models and repositories exist, but local report history is stored in a thread-safe in-memory store.
- It does not currently use Redis in the request path. A Redis client factory and Docker Compose Redis service exist.
- It requires PostgreSQL/pgvector for runtime RAG retrieval after ingestion. The older file-backed RAG artifacts remain only as offline/unit-test utilities.
- It does not currently enforce real SSO, RBAC, row-level customer authorization, or production secrets management.
- It does not currently implement a full human approval workflow UI. Approval gate logic exists as a policy abstraction.
- It does not guarantee that a configured external LLM will always return schema-valid JSON. The OpenAI-compatible client validates responses against Pydantic schemas and will fail if invalid JSON is returned.

## Why This Is Not Just a Chatbot

The workbench is not a free-form conversational assistant wrapped around an AML prompt. It is structured around routed, role-aware workflows and controlled evidence handling.

Key differences:

- Role-aware routing: Requests are routed by `role`, `task_type`, and optional `selected_agents`.
- Specialized agents: Each agent has a narrow responsibility, such as transaction behaviour, model explanation, typology mapping, feature critique, evidence assembly, judge review, or guardrail review.
- Typed outputs: LLM-backed agents produce Pydantic-validated structured outputs, not only free text.
- Evidence assembly: Final reports are composed from the outputs of agents that actually executed.
- Guardrails: Input, output, tool, PII, and approval policy layers exist in the backend.
- Evaluation: A judge panel scores final output quality and can fail a run when compliance issues are severe or the aggregate score is below threshold.
- Tool governance: Internal tools are allowlisted, schema-validated, role-scoped, audited, timeout-controlled, and denied when policy fails.
- Auditability: Responses include run IDs, executed agents, route explanations, judge scores, guardrail status, and audit traces.

## How the System Combines Analytics, ML Outputs, RAG, Agents, Guardrails, and Evaluation

The current system combines several layers:

1. Structured AML analytics:
   The local `DataService` reads synthetic CSV files for customers, transactions, customer features, and model outputs. It computes transaction lists, feature summaries, model output summaries, and counterparty network summaries.

2. ML outputs:
   The model explanation agent now uses `ModelService.score_customer` when trained artifacts are available. The v1 model is an offline-trained Isolation-Forest-style anomaly scorer over real-data customer features. If artifacts are missing or the customer is absent, the system returns an explicit no-artifact envelope rather than assumed scores.

3. Retrieval augmented generation:
   The typology mapping agent uses a `KnowledgeRetriever` abstraction. The active runtime implementation uses PostgreSQL/pgvector populated by `python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml`. Chunks preserve section headings, official source metadata, retrieval priority, and citation URLs. If the pgvector store is missing, retrieval fails loudly instead of silently falling back to sample files.

4. Multi-agent orchestration:
   The `RoleAwareRouter` resolves the route. The `DynamicGraphBuilder` builds a LangGraph `StateGraph` for only the selected route and falls back to a sequential runner if LangGraph is unavailable.

5. Guardrails:
   Input guardrails block prompt extraction, unsafe laundering instructions, and placeholder unauthorized access conditions. Output guardrails detect prohibited phrases, unsupported typology claims, fabricated citation risk, model-score-as-proof language, and PII. Tool guardrails block unsupported or unauthorized tool use. Approval gates identify sensitive actions that require human approval.

6. Evaluation:
   The judge panel runs six judges: faithfulness, citation, compliance, typology, data science, and usefulness. The system evaluation layer also generates golden cases and scores route correctness, guardrail correctness, citation presence, RAG relevance, faithfulness, answer relevance, compliance safety, model explanation quality, and latency.

7. Report packaging:
   Evidence assembly creates a role-aware Markdown report with sections driven by the agents that actually executed. The frontend renders the final report, judge cards, executed agents, structured outputs, evidence table, and audit metadata.

8. Storage and audit:
   The current API response path writes run details to an in-memory `RunStore`. ORM models for agent runs, steps, reports, audit logs, and judge results exist for later PostgreSQL-backed persistence. The tool registry emits audit events through the logging facade.

## Current User Journey

1. A user opens the Next.js workbench and selects a role, task type, customer ID, query, and optional manual agents.
2. The frontend shows a route preview using its local route catalog.
3. The frontend posts the analysis request to `POST /api/v1/analysis`.
4. The backend input policy evaluates the query.
5. The backend router resolves the authorized agent route.
6. The dynamic graph executes the selected agents in order.
7. Agent nodes retrieve structured sample data, model outputs, or knowledge documents as needed.
8. The evidence assembly agent composes a report from available agent outputs.
9. The judge panel evaluates the report.
10. Output guardrails review and possibly rewrite or block the response.
11. The response returns run ID, executed agents, final report, judge scores, guardrail status, route explanation, agent outputs, and audit trace.
12. The frontend renders the governed report and stores history through backend report endpoints backed by the in-memory run store.

## Current Implementation Status

Implemented and active:

- FastAPI routes for health, roles, analysis, and reports.
- Next.js pages for home, roles, analysis, history, and report detail.
- Role-aware router and partial-agent execution.
- LangGraph-compatible dynamic graph execution.
- Deterministic mock LLM client and OpenAI-compatible client abstraction.
- Local synthetic AML data access plus real-data fallback access for trained feature artifacts and transaction channel CSVs.
- Offline real-data feature building and Isolation-Forest-style model scoring.
- Official-source RAG manifest, pgvector ingestion command, section chunking, local deterministic embeddings, pgvector retrieval, and citation-ready chunks.
- Generated golden dataset builder, evaluation runner, evaluation API endpoints, and frontend evaluation dashboard.
- Structured schemas for agent outputs and judge outputs.
- Input/output/tool/PII guardrails.
- LLM-as-judge panel with weighted aggregation.
- In-memory run history.
- Tests for routing, graph execution, data service, tools, schemas, guardrails, evaluation, health, pgvector RAG, evaluation API, and LLM-backed agent schemas.

Implemented as foundation or placeholder:

- PostgreSQL ORM models and repositories.
- Redis client factory.
- Telemetry facade for future LangSmith, Phoenix, or OpenTelemetry integration.
- Approval gate policy abstraction.
- SSO placeholder in the frontend shell.

Not implemented:

- Production authentication and authorization.
- Live bank data integration.
- Durable persistence of analysis responses through the active API path.
- Full human approval workflow UI.
- External case management or regulatory reporting integration.
