"""pgvector RAG runtime tests."""

import pytest

from app.rag.pgvector_store import HashingEmbedder, PgVectorKnowledgeRetriever


class FailingEngine:
    """Minimal engine stand-in that simulates an unavailable pgvector store."""

    def connect(self) -> None:
        raise RuntimeError("database unavailable")


def test_hashing_embedder_returns_fixed_normalized_vector() -> None:
    """pgvector storage needs fixed-size local embeddings for every query and chunk."""
    embedder = HashingEmbedder(dimension=32)

    vector = embedder.embed("FINTRAC suspicious transaction indicators and rapid movement of funds")

    assert len(vector) == 32
    assert any(value != 0 for value in vector)
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_pgvector_retriever_fails_loudly_when_store_is_missing() -> None:
    """Runtime retrieval should tell operators to ingest pgvector data instead of silently falling back."""
    retriever = PgVectorKnowledgeRetriever(engine=FailingEngine())

    with pytest.raises(RuntimeError, match="python -m app.rag.ingest_pgvector"):
        retriever.search("FINTRAC indicators", limit=3)
