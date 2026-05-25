# AML Agentic Intelligence Workbench

A governed, self-evaluating multi-agent AML intelligence platform designed to help bank AML data science teams understand customer transaction behaviour, explain model outputs, map suspicious patterns to FINTRAC typologies, and identify potential feature gaps.

This repository currently contains the production-oriented backend foundation: FastAPI routes, typed schemas, role-aware routing placeholders, LangGraph-compatible state, persistence models, secure internal tool abstractions, synthetic AML sample data, service abstractions, Docker Compose infrastructure, and tests.

## Structure

```text
aml_agentic_workbench/
  backend/
    app/
      api/routes/
      agents/
      core/
      evaluation/
      guardrails/
      schemas/
      services/
      storage/
      tests/
      tools/
    data/sample/
    Dockerfile
    pyproject.toml
docker-compose.yml
.env.example
```

## Local Setup

Optionally copy the example environment file if you want to override local defaults:

```bash
cp .env.example .env
```

Start PostgreSQL, Redis, and the API:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Supported roles:

```bash
curl http://localhost:8000/api/v1/roles
```

Create a stubbed analysis run:

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "role": "data_scientist",
    "task_type": "feature_critique",
    "customer_id": "C-123",
    "query": "Critique the AML behavioural velocity features for this customer.",
    "require_full_report": false
  }'
```

## Running Tests Locally

From the backend directory:

```bash
cd aml_agentic_workbench/backend
python -m pip install -e ".[dev]"
pytest
```

## Frontend

The Next.js workbench lives in `aml_agentic_workbench/frontend`.

```bash
cd aml_agentic_workbench/frontend
pnpm install
pnpm dev
```

Set the backend API URL if needed:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 pnpm dev
```

The frontend includes role selection, dynamic route preview, analysis execution, report detail, judge score cards, guardrail status, evidence tables, and local run history.

## Design Notes

- No real LLM calls are implemented yet. Agent execution is stubbed behind clean routing and graph interfaces.
- Internal tools are registered, typed, allowlisted, role-scoped, audited, and executed with timeout/error handling. There is no arbitrary code or shell execution tool.
- Agents use a provider-neutral `LLMClient` abstraction. If `OPENAI_API_KEY` is unset, the backend runs with deterministic mock LLM outputs. If set, it can call an OpenAI-compatible `/chat/completions` endpoint through environment configuration.
- Local sample data is synthetic and lives under `aml_agentic_workbench/backend/data/sample`.
- Configuration is environment-driven through `pydantic-settings`.
- PostgreSQL models are defined with SQLAlchemy 2.0 and use `JSONB` for extensible run, report, audit, and judge metadata.
- Docker Compose uses `pgvector/pgvector:pg16` as the default PostgreSQL image to support future vector retrieval.
- Telemetry is represented by a provider-neutral tracing facade that can later route to LangSmith, Phoenix, or OpenTelemetry exporters.
