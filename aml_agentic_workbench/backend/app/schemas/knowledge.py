"""Knowledge retrieval schemas."""

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """A retrievable AML knowledge document."""

    doc_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    section: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoredKnowledgeDocument(KnowledgeDocument):
    """Knowledge document with a local retrieval score."""

    score: float = Field(..., ge=0.0)

