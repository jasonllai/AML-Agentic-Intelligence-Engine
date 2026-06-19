# AML Agentic Intelligence Workbench - System Overview

## Executive Summary

The AML Agentic Intelligence Workbench is a governed, role-aware application for AML analytics. The current implementation focuses on a realistic two-step operating model:

1. Data Science generates model-prioritized investigation candidates from the modeled customer population.
2. Investigation reviews one model-prioritized customer, gathers evidence, maps typology indicators carefully, recommends a disposition, and returns structured feedback for model evaluation.

The implementation includes a FastAPI backend, a Next.js frontend, dynamic route validation, a bounded Investigator planner/critic loop, deterministic mock-or-OpenAI-compatible LLM support, local real-data access, local model artifacts, four unsupervised anomaly scoring families, SHAP and reconstruction-error explanations, pgvector-backed official-source RAG retrieval, guardrails, LLM-as-judge evaluation, an evaluation dashboard, and in-memory run history.

## Business Purpose

AML teams operate across disconnected artifacts: transaction-channel records, KYC context, engineered feature tables, model scores, typology guidance, analyst review, validation evidence, and governance requirements. This workbench provides a controlled way to assemble those inputs into explainable, role-specific AML intelligence packages.

The current system supports:

- Population-level model prioritization for Data Science.
- Investigator-ready Detection Candidate Packages.
- Safe interpretation of model scores as prioritization evidence, not proof.
- Case-level transaction and KYC evidence review.
- Careful typology mapping with official-source citations when retrieval is available.
- Structured disposition and feedback capture.
- Repeatable quality review through judge scores, deterministic guardrails, route explanations, and audit traces.

## Primary Users

### Data Scientist

The Data Scientist user owns model-driven prioritization and candidate handoff.

The workflow supports:

- Scoring the modeled population across four model families.
- Comparing unsupervised model result sets.
- Reviewing thresholds and alert-volume rationale.
- Inspecting top feature drivers.
- Using SHAP explanations for Isolation Forest candidates.
- Using reconstruction-error contribution for Autoencoder, VAE, and CVAE candidates.
- Sending a governed candidate package to the Investigator workflow.

Primary task:

```text
generate_model_driven_candidates
```

### Investigator

The Investigator user owns case-level evidence review and feedback.

The workflow supports:

- Opening a model-prioritized customer from a Data Scientist handoff link.
- Reviewing transaction behaviour, feature context, and typology indicators.
- Using a bounded planner to gather required evidence.
- Producing a governed report after critic, judge, and guardrail review.
- Returning disposition and feedback fields for model evaluation.

Primary task:

```text
investigate_model_prioritized_candidate
```

## Governance and Evaluation Users

Model validation and compliance strategy concerns are still represented in the system, but they are not primary frontend roles.

They appear through:

- Data science quality judge checks.
- Compliance and typology judge checks.
- Output guardrails.
- Official-source RAG citation expectations.
- Golden-dataset evaluation metrics.
- Approval-gate abstractions for future sensitive actions.

`model_validator` and `compliance_strategy` are intentionally rejected by the current `SupportedRole` schema.

## Problems the System Solves

- Fragmented handoff: Data Scientist output is packaged as Detection Candidate Packages with model evidence, feature drivers, limitations, and disclaimers.
- Overbroad AI execution: The router limits execution by role and task, and the Investigator runner bounds planner actions.
- Unsafe model interpretation: Candidate packages and reports must preserve the boundary that model output is prioritization only.
- Unsupported typology claims: Typology mapping uses retrieved AML knowledge and citations; output guardrails flag unsupported claims.
- Weak auditability: Responses include run IDs, executed agents, route explanations, planner decisions, critic reviews, judge scores, guardrail outcomes, and audit traces.
- Inconsistent quality: Judge and guardrail layers distinguish judge warnings from actual guardrail failures.
- Local data opacity: The customer-data browser exposes the real-data sources and rows used for case review.

## What the System Does Not Do

The current codebase deliberately does not implement several enterprise capabilities:

- It does not make final AML decisions, confirm criminal activity, or direct users to file regulatory reports.
- It does not replace investigator judgment, model validation governance, or compliance approval workflows.
- It does not connect to live bank systems, case management platforms, sanctions systems, or regulatory reporting tools.
- It does not persist analysis responses to PostgreSQL in the request path. Local history uses an in-memory `RunStore`.
- It does not use Redis in the active request path.
- It does not enforce production SSO, RBAC, row-level customer authorization, secrets management, or migrations.
- It does not implement a full human approval workflow UI or export endpoint.
- It does not guarantee an external LLM will return schema-valid JSON; the OpenAI-compatible client validates and fails on invalid JSON.

## Why This Is Not Just a Chatbot

The workbench is structured around routed, role-aware workflows and controlled evidence handling.

Key differences:

- Role contracts: Data Scientist and Investigator workflows have distinct responsibilities.
- Specialized agents: Candidate ranking, planner, transaction behaviour, typology mapping, case investigation, evidence assembly, report critic, judge panel, and guardrail review each have narrow responsibilities.
- Typed outputs: LLM-backed agents produce Pydantic-validated structured outputs.
- Deterministic evidence: Model rank, score, threshold, and feature drivers come from model services, not LLM judgment.
- Guarded generation: Candidate explanations and final reports are evaluated by deterministic guardrails.
- Evaluation: System evaluation checks routing, guardrails, citations, RAG relevance, faithfulness, answer relevance, compliance safety, model explanation quality, and latency.
- Auditability: Responses include route and execution metadata rather than only free text.

## System Layers

### Structured Data

`DataService` reads local real-data files:

- Transaction channels: ABM, card, cheque, EFT, EMT, Western Union, and wire.
- KYC files: individual, small business, occupation lookup, and industry lookup.
- Model feature matrix: `artifacts/models/customer_features.csv`.

The `/customer-data` frontend page and `/api/v1/customer-data` API expose customer-scoped source records.

### Model Scoring

`ModelService` scores customers through `IsolationForestModelService`.

Supported model result families:

- Isolation Forest.
- Autoencoder.
- Variational Autoencoder.
- Conditional Variational Autoencoder.

Isolation Forest artifacts are trained offline. Deep-model prototype artifacts are trained deterministically on first use if missing. All scores are normalized to `[0, 1]` and treated as investigation prioritization only.

### Retrieval Augmented Generation

Runtime typology retrieval uses PostgreSQL/pgvector populated by:

```bash
python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml
```

If pgvector is unavailable, generic typology routes fail loudly. The primary Investigator handoff route has a narrow local keyword fallback with an explicit limitation note for local workflow continuity.

### Agent Orchestration

The router resolves role/task routes and validates selected agents. Generic routes use the LangGraph-compatible dynamic graph builder.

The primary Investigator task uses `InvestigatorAgenticRunner`, which:

- Streams planner and execution events.
- Enforces required evidence actions.
- Runs report critic review.
- Allows one refinement pass.
- Runs judge and guardrail review.
- Allows one guardrail remediation pass for fixable flags.

### Guardrails

Guardrails cover:

- Prompt injection and unsafe request patterns.
- Prohibited AML certainty language.
- STR instruction language.
- Unsupported typology claims.
- Citation mismatches.
- Model-score-as-proof language.
- PII redaction checks.
- Unsafe candidate explanation wording.

### Evaluation

The judge panel evaluates faithfulness, citations, compliance, typology wording, data science quality, and usefulness.

The system evaluation layer generates golden cases and records metrics in memory. The frontend `/evaluations` page shows runs, metric cards, failure rows, case detail, citations, and judge rationale.

### Storage and Audit

The active API response path stores run details in an in-memory `RunStore`. ORM models for agent runs, steps, reports, audit logs, and judge results exist for future durable persistence.

## Current User Journey

### Data Scientist

1. User opens `/roles/data_scientist`.
2. User runs `Generate model-driven investigation candidates`.
3. Backend scores the population across four model families.
4. Candidate packages are created with drivers, explanations, limitations, and disclaimers.
5. Frontend renders a result-list selector for each model family and the intersection.
6. User opens an Investigator handoff link for a candidate.

### Investigator

1. User opens `/roles/investigator`, optionally prefilled from a handoff link.
2. User runs `Investigate model-prioritized candidate`.
3. Frontend streams planner decisions, agent completions, critic review, remediation, and final governance events.
4. Backend gathers transaction behaviour, typology context, and candidate case review.
5. Evidence assembly creates a report.
6. Report critic may request one refinement.
7. Judge panel and guardrail review evaluate the final package.
8. Frontend renders the governed AML intelligence package, candidate context, investigator feedback, citations, decision/refinement details, evidence, and audit trail.

## Current Implementation Status

Implemented and active:

- FastAPI routes for health, roles, analysis, streaming analysis, reports, customer data, and evaluations.
- Next.js pages for home, role catalog, role workspaces, history, report detail, customer-data browsing, and evaluations.
- Data Scientist four-model workbench and candidate packages.
- Investigator bounded planner/critic/governance runner.
- Deterministic mock LLM and OpenAI-compatible client abstraction.
- Local real-data access and model feature artifacts.
- Offline Isolation Forest training and local prototype deep-model scoring.
- SHAP Isolation Forest explanations and reconstruction-error deep-model explanations.
- Pgvector RAG ingestion and runtime retrieval.
- Narrow local keyword fallback for the primary Investigator route when pgvector is unavailable.
- Structured schemas for agent outputs, candidate packages, and judge outputs.
- Input/output/tool/PII guardrails and candidate explanation guardrails.
- Golden-dataset evaluation API and dashboard.
- In-memory run and evaluation history.

Implemented as foundation or placeholder:

- PostgreSQL ORM models and repositories.
- Redis client factory.
- Telemetry facade.
- Approval gate policy abstraction.
- Frontend SSO/export placeholders.

Not implemented:

- Production authentication and authorization.
- Durable report persistence through PostgreSQL.
- Live bank data integration.
- Full human approval workflow UI.
- External case-management or regulatory-reporting integration.
- Production-grade embedding model or governed model registry.
