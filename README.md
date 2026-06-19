# AML Agentic Intelligence Workbench

A governed AML analytics workbench for model-driven candidate generation and investigator review. The current system is organized around two primary bank operating roles:

- Data Scientist: score the modeled customer population with four unsupervised anomaly models, explain top candidates, and create governed investigation handoff packages.
- Investigator: review one model-prioritized customer, gather evidence, map typology indicators carefully, produce a disposition recommendation, and return model-feedback fields.

The application includes a FastAPI backend, a Next.js frontend, dynamic agent routing, a bounded Investigator planner/critic loop, local real-data access, offline model artifacts, pgvector-backed AML knowledge retrieval, deterministic guardrails, LLM-as-judge evaluation, in-memory run history, and Docker Compose infrastructure.

## Current System Design

```mermaid
flowchart TD
    A[Data Scientist workflow] --> B[Candidate Ranking Agent]
    B --> C[Four model population scoring]
    C --> D[Detection Candidate Packages]
    D --> E[Investigator handoff link]
    E --> F[Investigator workflow]
    F --> G[Supervisor Planner]
    G --> H[Transaction Behaviour Agent]
    H --> I[Typology Mapping Agent]
    I --> J[Case Investigation Agent]
    J --> K[Evidence Assembly]
    K --> L[Report Critic]
    L --> M[Judge Panel]
    M --> N[Guardrail Review]
    N --> O[Governed AML Intelligence Package]
```

Primary routes:

| Role | Task | Runtime path |
| --- | --- | --- |
| `data_scientist` | `generate_model_driven_candidates` | `candidate_ranking_agent` -> `guardrail_agent`, plus candidate-level explanation guardrails |
| `investigator` | `investigate_model_prioritized_candidate` | bounded planner, transaction behaviour, typology mapping, case investigation, evidence assembly, critic, judge panel, guardrail |

Legacy/generic task types still exist in backend contracts for route and evaluation coverage, but the frontend exposes the two primary workflows above.

## What Is Implemented

- FastAPI API under `/api/v1` for health, roles, analysis, streaming Investigator analysis, reports, customer-data browsing, and evaluations.
- Next.js App Router frontend with role workspaces, live Investigator execution timeline, four-model candidate results, report history, customer-data browser, and evaluation dashboard.
- Four-model Data Scientist workbench:
  - Isolation Forest.
  - Autoencoder.
  - Variational Autoencoder.
  - Conditional Variational Autoencoder.
  - Intersection list for customers appearing across all four top-10 lists.
- Model explanations:
  - Isolation Forest uses model-agnostic SHAP over the local anomaly score function.
  - Autoencoder/VAE/CVAE use reconstruction-error contribution details.
  - Candidate explanations may use an LLM only to summarize deterministic model evidence; unsafe LLM text falls back to deterministic wording.
- Investigator workflow:
  - Streams planner decisions, agent completions, critic feedback, remediation events, and final response over `/api/v1/analysis/stream`.
  - Enforces bounded evidence actions in order.
  - Allows at most one critic refinement and one guardrail remediation pass.
- Real-data layer:
  - Reads local transaction-channel and KYC CSVs from `real_data/`.
  - Reads model feature rows from `artifacts/models/customer_features.csv`.
  - Exposes customer-scoped evidence through `/api/v1/customer-data`.
- RAG:
  - Runtime typology retrieval uses PostgreSQL with pgvector after ingestion.
  - The primary Investigator handoff route has a narrow local keyword fallback when pgvector is unavailable locally.
- Governance:
  - Input, output, PII, tool, approval-gate, and policy-engine guardrails.
  - LLM-as-judge panel for faithfulness, citations, compliance, typology wording, data science quality, and usefulness.
  - Golden-dataset evaluation API and dashboard.

## Repository Structure

```text
aml_agentic_workbench/
  backend/
    app/
      agents/        Router, LangGraph-compatible graph, agent nodes, Investigator runner
      api/routes/    FastAPI endpoints
      core/          Settings, constants, logging, security placeholder
      evaluation/    Judge panel, golden dataset, evaluation runner
      guardrails/    Input/output/tool/PII policy and approval gates
      llm/           Mock and OpenAI-compatible LLM clients, prompts, schemas
      ml/            Feature builder, local models, SHAP explanations
      rag/           File-backed and pgvector ingestion/retrieval utilities
      schemas/       API and domain schemas
      services/      Data, candidates, run store, audit, database, Redis, telemetry
      storage/       SQLAlchemy ORM foundation
      tests/         Backend tests
      tools/         MCP-style internal tool registry
    Dockerfile
    pyproject.toml
  frontend/
    app/             Next.js pages
    components/      Role workspace, report view, execution timeline, UI primitives
    lib/             API wrapper and route catalog
    types/           TypeScript API contracts
artifacts/
  models/            Local trained model artifacts, ignored by git
  rag/               Optional file-backed RAG artifacts for tests/offline work
real_data/           Local transaction, KYC, and label CSV inputs
docs/                Architecture, workflows, RAG, modeling, evaluation notes
docker-compose.yml
```

## Local Setup

Optionally copy the sample environment file:

```bash
cp .env.example .env
```

Start PostgreSQL, Redis, and the backend API:

```bash
docker compose up --build
```

The API is available at:

```text
http://localhost:8000/api/v1
```

Run the frontend:

```bash
cd aml_agentic_workbench/frontend
pnpm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 pnpm dev
```

The frontend defaults to `http://localhost:8000/api/v1` when `NEXT_PUBLIC_API_BASE_URL` is not set.

## Model and RAG Artifacts

Train local model artifacts from the repository root data files:

```bash
cd aml_agentic_workbench/backend
python -m app.ml.train_model --data-dir real_data --artifact-dir ../../artifacts/models
```

Ingest official-source RAG content into PostgreSQL/pgvector:

```bash
cd aml_agentic_workbench/backend
python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml
```

If you copied `.env.example` and run this command from the host instead of inside Docker, set `DATABASE_URL=postgresql+psycopg://aml:aml@localhost:5432/aml_workbench` for the ingestion process.

If model artifacts are missing, model endpoints return explicit `model_artifact_required` style outputs instead of inventing scores. If pgvector is missing, typology routes fail loudly except for the primary Investigator handoff route, which uses a narrow local keyword fallback for local review continuity.

## API Examples

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Supported roles:

```bash
curl http://localhost:8000/api/v1/roles
```

Generate Data Scientist candidate packages:

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "role": "data_scientist",
    "task_type": "generate_model_driven_candidates",
    "query": "Generate ranked model-driven AML investigation candidates for investigator handoff.",
    "require_full_report": false
  }'
```

Run an Investigator case review:

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "role": "investigator",
    "task_type": "investigate_model_prioritized_candidate",
    "customer_id": "SYNID0100000167",
    "query": "Investigate this model-prioritized candidate and return case feedback.",
    "require_full_report": false
  }'
```

Browse local customer evidence:

```bash
curl "http://localhost:8000/api/v1/customer-data/customer/SYNID0200567030?source=all&limit=25"
```

## Running Tests

Backend:

```bash
cd aml_agentic_workbench/backend
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check app
```

Frontend:

```bash
cd aml_agentic_workbench/frontend
pnpm install
pnpm typecheck
pnpm build
```

`pnpm lint` is declared but this repository does not include a committed Next.js ESLint configuration, so `pnpm typecheck` and `pnpm build` are the current frontend verification commands.

## Important Boundaries

- The system supports AML investigation prioritization and evidence organization. It does not make final AML decisions, confirm criminal activity, or instruct users to file regulatory reports.
- Model output is prioritization evidence only. Every candidate package includes the required disclaimer that model output is not proof of suspicious activity and does not by itself support an STR decision.
- Runtime report history and evaluation runs are stored in process memory. SQLAlchemy models and PostgreSQL infrastructure exist, but durable report persistence is not active in the request path.
- Redis is available through Docker Compose and a client factory but is not used by the active analysis, routing, retrieval, report, or evaluation path.
- Production authentication, authorization, row-level customer access control, secrets management, migrations, external case-management integration, and full human approval workflow UI are not implemented.
