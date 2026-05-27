"""Knowledge retrieval abstractions and local keyword implementation."""

import json
import re
from abc import ABC, abstractmethod
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.rag.ingest import CHUNKS_FILENAME, EMBEDDINGS_FILENAME, VECTORIZER_FILENAME, LocalTfidfVectorizer
from app.rag.pgvector_store import PgVectorKnowledgeRetriever
from app.schemas.knowledge import KnowledgeDocument, ScoredKnowledgeDocument
from app.services.data_service import default_sample_data_dir
from app.services.database import engine


class KnowledgeRetriever(ABC):
    """Interface for AML knowledge retrieval implementations."""

    @abstractmethod
    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Return relevant documents for a query."""


class LocalKeywordRetriever(KnowledgeRetriever):
    """Simple deterministic keyword retriever over local JSONL documents."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_sample_data_dir() / "aml_knowledge_base.jsonl"
        self._documents = self._load_documents(self.path)

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Score documents using token overlap and return the top matches."""
        query_terms = self._tokens(query)
        if not query_terms:
            return []

        scored: list[ScoredKnowledgeDocument] = []
        query_counts = Counter(query_terms)
        for document in self._documents:
            haystack = " ".join([document.title, document.section, document.text, " ".join(document.metadata.keys())])
            doc_counts = Counter(self._tokens(haystack))
            score = sum(min(query_counts[token], doc_counts[token]) for token in query_counts)
            if score > 0:
                scored.append(ScoredKnowledgeDocument(**document.model_dump(), score=float(score)))

        scored.sort(key=lambda document: (-document.score, document.doc_id))
        return scored[:limit]

    @staticmethod
    def _load_documents(path: Path) -> list[KnowledgeDocument]:
        if not path.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {path}")
        documents: list[KnowledgeDocument] = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    documents.append(KnowledgeDocument.model_validate(json.loads(line)))
        return documents

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", value.lower())


class VectorRetriever(KnowledgeRetriever):
    """Deprecated placeholder retained for compatibility with older imports."""

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Runtime vector retrieval is implemented by PgVectorKnowledgeRetriever."""
        return PgVectorKnowledgeRetriever(engine=engine).search(query, limit=limit)


class SemanticKnowledgeRetriever(KnowledgeRetriever):
    """Local semantic retriever over offline-built official-source RAG artifacts."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self._documents = self._load_chunks()
        vectorizer_payload = json.loads((self.artifact_dir / VECTORIZER_FILENAME).read_text(encoding="utf-8"))
        self._vectorizer = LocalTfidfVectorizer.from_dict(vectorizer_payload)
        raw_matrix = json.loads((self.artifact_dir / EMBEDDINGS_FILENAME).read_text(encoding="utf-8"))
        self._matrix = [{int(key): float(value) for key, value in row.items()} for row in raw_matrix]

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Return citation-ready chunks ranked by local semantic similarity."""
        if not query.strip() or not self._documents:
            return []
        query_vector = self._vectorizer.transform([query])[0]
        scores = [_cosine_similarity(query_vector, vector) for vector in self._matrix]
        ranked_indexes = sorted(range(len(scores)), key=lambda index: (-scores[index], self._documents[index].doc_id))
        results: list[ScoredKnowledgeDocument] = []
        for index in ranked_indexes[:limit]:
            if scores[index] <= 0:
                continue
            results.append(
                ScoredKnowledgeDocument(
                    **self._documents[index].model_dump(mode="json"),
                    score=round(float(scores[index]), 6),
                )
            )
        return results

    def _load_chunks(self) -> list[KnowledgeDocument]:
        path = self.artifact_dir / CHUNKS_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"RAG chunks artifact not found: {path}")
        documents: list[KnowledgeDocument] = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    documents.append(KnowledgeDocument.model_validate_json(line))
        return documents

@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    """Return the required pgvector-backed runtime retriever."""
    return PgVectorKnowledgeRetriever(engine=engine)


def _cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left).intersection(right)
    numerator = sum(left[index] * right[index] for index in shared)
    left_norm = sum(value * value for value in left.values()) ** 0.5
    right_norm = sum(value * value for value in right.values()) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _resolve_artifact_dir(path: Path) -> Path:
    if path.exists():
        return path
    root_candidate = Path(__file__).resolve().parents[4] / path
    return root_candidate if root_candidate.exists() else path
