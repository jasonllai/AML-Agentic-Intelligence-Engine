"""PostgreSQL/pgvector storage and retrieval for official-source AML RAG."""

import hashlib
import json
import math
import re
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from app.rag.semantic import RagSource
from app.schemas.knowledge import KnowledgeDocument, ScoredKnowledgeDocument

EMBEDDING_DIMENSION = 384
INGEST_COMMAND = "python -m app.rag.ingest_pgvector --manifest config/rag_sources.yaml"


class RagStoreUnavailable(RuntimeError):
    """Raised when the required pgvector RAG runtime store is unavailable."""


class HashingEmbedder:
    """Deterministic local embedding backend suitable for offline pgvector ingestion."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def embed(self, text_value: str) -> list[float]:
        """Embed text into a fixed-size normalized vector using token and bigram hashing."""
        tokens = re.findall(r"[a-z0-9]+", text_value.lower())
        vector = [0.0] * self.dimension
        features = [*tokens, *[f"{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False)]]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, byteorder="big", signed=False)
            index = raw % self.dimension
            sign = 1.0 if ((raw >> 8) & 1) == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]


def ensure_pgvector_schema(engine: Engine, dimension: int = EMBEDDING_DIMENSION) -> None:
    """Create pgvector tables needed by runtime retrieval and offline ingestion."""
    with engine.begin() as connection:
        statements = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            """
            CREATE TABLE IF NOT EXISTS rag_source_documents (
                source_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                organization TEXT NOT NULL,
                url TEXT NOT NULL,
                document_type TEXT NOT NULL,
                jurisdiction TEXT NOT NULL,
                priority INTEGER NOT NULL,
                topics JSONB NOT NULL DEFAULT '[]'::jsonb,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES rag_source_documents(source_id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                section TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                url TEXT,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({dimension}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_ingestion_runs (
                run_id TEXT PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                source_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_ingestion_failures (
                failure_id BIGSERIAL PRIMARY KEY,
                run_id TEXT REFERENCES rag_ingestion_runs(run_id) ON DELETE CASCADE,
                source_id TEXT,
                url TEXT,
                error TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
        ]
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_rag_chunks_source_id ON rag_chunks(source_id)"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding "
                "ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
        )


def replace_pgvector_documents(
    *,
    engine: Engine,
    sources: Sequence[RagSource],
    chunks_by_source: dict[str, Sequence[KnowledgeDocument]],
    embedder: HashingEmbedder | None = None,
    run_id: str,
    failures: Sequence[dict[str, str]] = (),
) -> dict[str, int]:
    """Replace all RAG source/chunk rows with a newly ingested official-source corpus."""
    embedder = embedder or HashingEmbedder()
    started_at = datetime.now(UTC)
    chunk_count = sum(len(chunks) for chunks in chunks_by_source.values())
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM rag_chunks"))
        connection.execute(text("DELETE FROM rag_source_documents"))
        connection.execute(
            text(
                """
                INSERT INTO rag_ingestion_runs (
                    run_id, started_at, source_count, chunk_count, failure_count, metadata
                )
                VALUES (:run_id, :started_at, :source_count, :chunk_count, :failure_count, CAST(:metadata AS jsonb))
                """
            ),
            {
                "run_id": run_id,
                "started_at": started_at,
                "source_count": len(sources),
                "chunk_count": chunk_count,
                "failure_count": len(failures),
                "metadata": json.dumps({"embedding_backend": "local_hashing", "dimension": embedder.dimension}),
            },
        )
        for source in sources:
            connection.execute(
                text(
                    """
                    INSERT INTO rag_source_documents (
                        source_id, title, organization, url, document_type, jurisdiction, priority, topics, metadata
                    )
                    VALUES (
                        :source_id, :title, :organization, :url, :document_type, :jurisdiction,
                        :priority, CAST(:topics AS jsonb), CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "source_id": source.id,
                    "title": source.title,
                    "organization": source.organization,
                    "url": source.url,
                    "document_type": source.document_type,
                    "jurisdiction": source.jurisdiction,
                    "priority": source.priority,
                    "topics": json.dumps(source.topics),
                    "metadata": json.dumps({"local_path": source.local_path}),
                },
            )
            for chunk in chunks_by_source.get(source.id, []):
                connection.execute(
                    text(
                        """
                        INSERT INTO rag_chunks (
                            chunk_id, source_id, title, source, section, chunk_text, url, metadata, embedding
                        )
                        VALUES (
                            :chunk_id, :source_id, :title, :source, :section, :chunk_text,
                            :url, CAST(:metadata AS jsonb), CAST(:embedding AS vector)
                        )
                        """
                    ),
                    {
                        "chunk_id": chunk.doc_id,
                        "source_id": source.id,
                        "title": chunk.title,
                        "source": chunk.source,
                        "section": chunk.section,
                        "chunk_text": chunk.text,
                        "url": chunk.url,
                        "metadata": json.dumps(chunk.metadata),
                        "embedding": _vector_literal(embedder.embed(_document_text(chunk))),
                    },
                )
        for failure in failures:
            connection.execute(
                text(
                    """
                    INSERT INTO rag_ingestion_failures (run_id, source_id, url, error)
                    VALUES (:run_id, :source_id, :url, :error)
                    """
                ),
                {
                    "run_id": run_id,
                    "source_id": failure.get("source_id"),
                    "url": failure.get("url"),
                    "error": failure["error"],
                },
            )
        connection.execute(
            text("UPDATE rag_ingestion_runs SET completed_at = :completed_at WHERE run_id = :run_id"),
            {"run_id": run_id, "completed_at": datetime.now(UTC)},
        )
    return {"source_count": len(sources), "chunk_count": chunk_count, "failure_count": len(failures)}


class PgVectorKnowledgeRetriever:
    """Runtime retriever backed by PostgreSQL pgvector."""

    def __init__(self, engine: Engine, embedder: HashingEmbedder | None = None) -> None:
        self.engine = engine
        self.embedder = embedder or HashingEmbedder()

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Return citation-ready chunks ranked by pgvector cosine distance."""
        if not query.strip():
            return []
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT
                            chunk_id, title, source, section, chunk_text, url, metadata,
                            1 - (embedding <=> CAST(:embedding AS vector)) AS score
                        FROM rag_chunks
                        ORDER BY embedding <=> CAST(:embedding AS vector), chunk_id
                        LIMIT :limit
                        """
                    ),
                    {"embedding": _vector_literal(self.embedder.embed(query)), "limit": limit},
                ).mappings()
                return [
                    ScoredKnowledgeDocument(
                        doc_id=row["chunk_id"],
                        title=row["title"],
                        source=row["source"],
                        section=row["section"],
                        text=row["chunk_text"],
                        url=row["url"],
                        metadata=dict(row["metadata"] or {}),
                        score=max(0.0, round(float(row["score"] or 0.0), 6)),
                    )
                    for row in rows
                ]
        except Exception as exc:
            raise RagStoreUnavailable(
                "pgvector RAG store is not initialized or unavailable. "
                f"Run `{INGEST_COMMAND}` after PostgreSQL/pgvector is running."
            ) from exc


def _document_text(document: KnowledgeDocument) -> str:
    return " ".join([document.title, document.section, document.text])


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
