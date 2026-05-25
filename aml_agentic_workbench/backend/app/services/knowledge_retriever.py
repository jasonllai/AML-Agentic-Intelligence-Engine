"""Knowledge retrieval abstractions and local keyword implementation."""

import json
import re
from abc import ABC, abstractmethod
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.schemas.knowledge import KnowledgeDocument, ScoredKnowledgeDocument
from app.services.data_service import default_sample_data_dir


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
    """Placeholder for pgvector or external vector database retrieval."""

    def search(self, query: str, limit: int = 3) -> list[ScoredKnowledgeDocument]:
        """Vector retrieval is intentionally not implemented in the foundation."""
        raise NotImplementedError("Vector retrieval will be implemented behind this interface.")


@lru_cache
def get_knowledge_retriever() -> KnowledgeRetriever:
    """Return the default local knowledge retriever."""
    return LocalKeywordRetriever()
