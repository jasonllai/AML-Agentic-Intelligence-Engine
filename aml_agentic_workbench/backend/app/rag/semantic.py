"""Semantic chunking and local embedding helpers for AML RAG."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.schemas.knowledge import KnowledgeDocument


@dataclass(frozen=True)
class RagSource:
    """Official-source RAG manifest entry."""

    id: str
    title: str
    organization: str
    url: str
    document_type: str
    jurisdiction: str
    priority: int
    topics: list[str]
    local_path: str | None = None


def load_source_manifest(path: Path) -> list[RagSource]:
    """Load official RAG source metadata from YAML."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [RagSource(**source) for source in payload.get("sources", [])]


def chunk_document(
    *,
    source_id: str,
    title: str,
    organization: str,
    url: str,
    document_type: str,
    jurisdiction: str,
    topics: list[str],
    priority: int,
    text: str,
    max_tokens: int = 220,
    overlap_tokens: int = 40,
) -> list[KnowledgeDocument]:
    """Chunk a document by markdown-style sections with token overlap."""
    sections = _split_sections(text)
    chunks: list[KnowledgeDocument] = []
    previous_tail: list[str] = []
    ordinal = 0
    for heading, body in sections:
        tokens = body.split()
        start = 0
        while start < len(tokens):
            window = tokens[start : start + max_tokens]
            chunk_tokens = [*previous_tail, *window] if previous_tail else window
            if chunk_tokens:
                chunks.append(
                    KnowledgeDocument(
                        doc_id=f"{source_id}:{ordinal:04d}",
                        title=title,
                        source=f"{organization} - {document_type}",
                        section=heading,
                        text=" ".join(chunk_tokens),
                        url=url,
                        metadata={
                            "source_id": source_id,
                            "organization": organization,
                            "document_type": document_type,
                            "jurisdiction": jurisdiction,
                            "topics": topics,
                            "retrieval_priority": priority,
                            "chunk_ordinal": ordinal,
                        },
                    )
                )
                ordinal += 1
            previous_tail = chunk_tokens[-overlap_tokens:] if overlap_tokens > 0 else []
            start += max_tokens
    return chunks


def extract_readable_text(html: str) -> str:
    """Extract readable text from HTML without adding a heavyweight parser dependency."""
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?i)</h[1-6]>", "\n\n", html)
    html = re.sub(r"(?i)<h[1-6][^>]*>", "\n\n# ", html)
    html = re.sub(r"(?i)</p>|<br\\s*/?>|</li>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "Overview"
    current_lines: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading:
            if current_lines:
                sections.append((current_heading, _clean_text("\n".join(current_lines))))
            current_heading = heading.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, _clean_text("\n".join(current_lines))))
    return [(heading, body) for heading, body in sections if body]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
