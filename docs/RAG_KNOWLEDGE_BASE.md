# RAG Knowledge Base

## Source Policy

The RAG knowledge base is restricted to official AML sources for v1.

Configured source groups:

- FINTRAC ML/TF indicators for financial entities.
- FINTRAC suspicious transaction reporting guidance.
- FINTRAC strategic intelligence and operational alerts.
- FATF Recommendations.
- FATF Risk-Based Approach Guidance for the Banking Sector.
- FATF Trade-Based Money Laundering Risk Indicators.
- Egmont Group FIU reference material.

The source manifest lives at:

```text
aml_agentic_workbench/backend/config/rag_sources.yaml
```

## Runtime Storage

The application runtime now requires PostgreSQL with pgvector for RAG retrieval.

Docker Compose uses:

```text
pgvector/pgvector:pg16
```

The runtime retriever is `PgVectorKnowledgeRetriever`. `get_knowledge_retriever()` no longer silently falls back to local JSON artifacts. If PostgreSQL, pgvector, or the RAG tables are unavailable, retrieval fails loudly with a message instructing the operator to run:

```bash
python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml
```

This is intentional. Typology and regulatory grounding should not depend on hidden sample files in production-like runs.

Exception: the primary Investigator handoff route, `investigate_model_prioritized_candidate`, catches pgvector unavailability inside `typology_mapping_agent` and uses `LocalKeywordRetriever` with an explicit limitation note. This narrow fallback exists so local candidate review remains usable before pgvector ingestion. Other typology/RAG routes still fail loudly.

## pgvector Schema

The pgvector ingestion command creates these tables if missing:

- `rag_source_documents`: one row per official source document.
- `rag_chunks`: section-aware chunks with citation metadata and a pgvector embedding.
- `rag_ingestion_runs`: ingestion run summary metadata.
- `rag_ingestion_failures`: failed source fetches with source ID, URL, and error.

The chunk table stores:

- Chunk ID.
- Source ID.
- Title.
- Source label.
- Section heading.
- Chunk text.
- Source URL.
- Enriched metadata.
- Fixed-size vector embedding.

## Ingestion Command

From `aml_agentic_workbench/backend`:

```bash
python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml
```

If this command runs from the host while PostgreSQL is started by Docker Compose, use a host-resolvable database URL such as `DATABASE_URL=postgresql+psycopg://aml:aml@localhost:5432/aml_workbench`. The Docker service name `postgres` is only resolvable inside the Compose network.

The command:

1. Reads the official-source YAML manifest.
2. Downloads or reads each source document.
3. Extracts readable text from HTML or PDF.
4. Chunks text by section with overlap.
5. Computes deterministic local fixed-size embeddings.
6. Creates pgvector extension, tables, and indexes if missing.
7. Replaces source/chunk rows in PostgreSQL.
8. Records failed source fetches instead of hiding them.

The older file-backed command remains in the codebase for unit tests and offline artifact experiments:

```bash
python -m app.rag.ingest --manifest config/rag_sources.yaml --artifact-dir ../../artifacts/rag
```

It is not the production runtime path.

## Chunking Strategy

The chunker:

- Splits source text by markdown or extracted heading boundaries.
- Preserves section heading.
- Applies controlled token overlap between chunks.
- Carries source URL and metadata into every chunk.

Chunk metadata includes:

- Source ID.
- Organization.
- Document type.
- Jurisdiction.
- Topics.
- Retrieval priority.
- Chunk ordinal.

## Embedding and Retrieval Strategy

The pgvector v1 embedding backend is local and deterministic. It hashes unigrams and bigrams into a fixed-size normalized vector so ingestion and query retrieval can run without external embedding APIs.

This is intentionally simple and reproducible for local/offline operation. It is less semantically rich than a transformer embedding model, but it gives the system a true vector database runtime and a stable interface that can later be upgraded.

Runtime retrieval:

1. Embeds the query with the same local hashing embedder.
2. Runs pgvector cosine-distance ranking over `rag_chunks`.
3. Returns `ScoredKnowledgeDocument` records with citation-ready fields.

Returned fields include:

- Title.
- Source.
- Section.
- Text.
- URL.
- Metadata.
- Similarity score.

## Agent Integration

The typology mapping agent receives retrieved pgvector chunks and passes them to the LLM prompt. Its output schema requires citations, and output guardrails still flag unsupported typology claims.

The citation policy is strict: typology or regulatory claims should cite retrieved official-source chunks.

For the primary Investigator fallback path, the same citation and careful-language policy applies to local keyword results, and the agent records the fallback limitation in its output.

## Evaluation

RAG is covered by the system evaluation framework:

- Golden cases tagged `rag`, `typology`, and `citation_required`.
- Citation presence metric.
- RAG retrieval relevance metric.
- Faithfulness judge.
- Answer relevance judge.
- Compliance safety checks.

The evaluation dashboard is available at:

```text
/evaluations
```

## Refresh Workflow

1. Review and update `config/rag_sources.yaml`.
2. Start PostgreSQL/pgvector through Docker Compose.
3. Run `python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml`.
4. Inspect ingestion run and failure tables for failed sources.
5. Run backend tests.
6. Run an analysis smoke test for a typology route. Use a generic typology route to verify pgvector is active; the primary Investigator route can succeed locally through its narrow keyword fallback.
7. Run the evaluation suite from the dashboard or API.

## Known Gaps

- FATF pages can block automated retrieval from some environments; failures are recorded for retry or manual mirroring.
- The local hashing embedding approach is deterministic but less expressive than modern embedding models.
- There is no scheduled refresh job yet.
- Analysis responses still use in-memory run storage; RAG itself is database-backed.
