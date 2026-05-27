# Evaluation Framework

## Purpose

The evaluation framework tests the full AML Workbench as a governed system, not only individual prompts or agent outputs.

It evaluates:

- Role/task routing.
- Partial and full agent execution.
- Guardrail behaviour.
- Required citation presence.
- RAG retrieval relevance.
- LLM-as-judge faithfulness.
- LLM-as-judge answer relevance.
- Compliance-safe wording.
- Model explanation quality.
- Case latency.

## Golden Dataset

Golden cases are generated in:

```text
aml_agentic_workbench/backend/app/evaluation/golden_dataset.py
```

Cases include:

- Real or configured customer IDs.
- Labeled and unlabeled customer coverage.
- Every supported role.
- Supported task routes that are valid for each role.
- Official-source RAG typology topics.
- Prompt-injection guardrail cases.
- Missing-customer model scoring cases.

Each case records:

- Case ID.
- Role.
- Task type.
- Customer ID.
- Query.
- Expected route and agents.
- Expected evidence requirements.
- Expected guardrail outcome.
- Citation requirement.
- Evaluation tags.

To generate a versioned JSONL artifact:

```bash
python -m app.evaluation.build_golden_dataset --output ../../artifacts/evaluation/golden_dataset_v1.jsonl --case-limit 100
```

Generated artifacts live under `artifacts/`, which is ignored by git.

## Runner

The runner lives in:

```text
aml_agentic_workbench/backend/app/evaluation/runner.py
```

It accepts golden cases and an analysis executor. In production API use, the executor calls the same `create_analysis` path used by `POST /api/v1/analysis`. Tests can inject a deterministic executor.

## Metrics

The v1 runner computes:

- `route_correctness`
- `guardrail_correctness`
- `citation_presence`
- `rag_retrieval_relevance`
- `faithfulness`
- `answer_relevance`
- `compliance_safety`
- `model_explanation_quality`
- `latency_ms`

Faithfulness uses the existing judge framework. Answer relevance uses a dedicated judge in `app/evaluation/answer_relevance_judge.py`.

## API

Evaluation endpoints:

```text
POST /api/v1/evaluations/generate-golden-dataset
POST /api/v1/evaluations/run
GET  /api/v1/evaluations
GET  /api/v1/evaluations/{run_id}
```

Run summaries are stored in memory for v1 through `app/services/evaluation_store.py`.

## Frontend

The dashboard is available at:

```text
/evaluations
```

It shows:

- Generate/run controls.
- Latest run status.
- Overall score.
- Metric cards.
- Failure table.
- Case detail with query, expected and actual routes, guardrail outcome, judge rationale, citations, and failure reasons.

## Operational Notes

- RAG cases require PostgreSQL/pgvector ingestion for full runtime success.
- If pgvector is missing, RAG retrieval fails loudly and evaluation records the failure.
- Mock LLM runs are deterministic and suitable for local regression checks.
- Real LLM-as-judge quality depends on configured OpenAI-compatible credentials.
