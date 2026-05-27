"""Offline ingestion for official-source AML RAG artifacts."""

import argparse
import json
import math
import re
from collections import Counter
from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

from app.rag.semantic import chunk_document, extract_readable_text, load_source_manifest

CHUNKS_FILENAME = "chunks.jsonl"
VECTORIZER_FILENAME = "vectorizer.joblib"
EMBEDDINGS_FILENAME = "embeddings.index"
MANIFEST_LOCK_FILENAME = "manifest.lock.json"


def build_rag_artifacts(manifest: Path, artifact_dir: Path) -> dict[str, int]:
    """Build local semantic retrieval artifacts from an official-source manifest."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sources = load_source_manifest(manifest)
    chunks = []
    failures = []
    for source in sources:
        try:
            text = _load_source_text(source.local_path, source.url)
        except Exception as exc:
            failures.append({"source_id": source.id, "url": source.url, "error": f"{exc.__class__.__name__}: {exc}"})
            continue
        chunks.extend(
            chunk_document(
                source_id=source.id,
                title=source.title,
                organization=source.organization,
                url=source.url,
                document_type=source.document_type,
                jurisdiction=source.jurisdiction,
                topics=source.topics,
                priority=source.priority,
                text=text,
            )
        )

    with (artifact_dir / CHUNKS_FILENAME).open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(chunk.model_dump_json() + "\n")

    vectorizer = LocalTfidfVectorizer()
    matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
    (artifact_dir / VECTORIZER_FILENAME).write_text(json.dumps(vectorizer.to_dict()), encoding="utf-8")
    (artifact_dir / EMBEDDINGS_FILENAME).write_text(json.dumps(matrix), encoding="utf-8")
    lock = {
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "failed_source_count": len(failures),
        "failures": failures,
        "sources": [source.__dict__ for source in sources],
    }
    (artifact_dir / MANIFEST_LOCK_FILENAME).write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return {"source_count": len(sources), "chunk_count": len(chunks)}


def _load_source_text(local_path: str | None, url: str) -> str:
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    response = httpx.get(
        url,
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "AML-Agentic-Workbench-RAG/0.1 (+official-source-ingestion)"},
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf_text(response.content)
    if "html" in content_type:
        return extract_readable_text(response.text)
    return response.text


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


class LocalTfidfVectorizer:
    """Small local TF-IDF vectorizer for offline AML RAG artifacts."""

    def __init__(self) -> None:
        self.vocabulary_: dict[str, int] = {}
        self.idf_: dict[str, float] = {}

    def fit_transform(self, documents: list[str]) -> list[dict[int, float]]:
        tokenized = [self._tokens(document) for document in documents]
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized:
            document_frequency.update(set(tokens))
        self.vocabulary_ = {token: index for index, token in enumerate(sorted(document_frequency))}
        total = max(len(documents), 1)
        self.idf_ = {token: math.log((1 + total) / (1 + count)) + 1 for token, count in document_frequency.items()}
        return [self._vector(tokens) for tokens in tokenized]

    def transform(self, documents: list[str]) -> list[dict[int, float]]:
        return [self._vector(self._tokens(document)) for document in documents]

    def to_dict(self) -> dict[str, object]:
        return {"vocabulary": self.vocabulary_, "idf": self.idf_}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LocalTfidfVectorizer":
        vectorizer = cls()
        vectorizer.vocabulary_ = {str(key): int(value) for key, value in dict(payload["vocabulary"]).items()}
        vectorizer.idf_ = {str(key): float(value) for key, value in dict(payload["idf"]).items()}
        return vectorizer

    def _vector(self, tokens: list[str]) -> dict[int, float]:
        counts = Counter(token for token in tokens if token in self.vocabulary_)
        if not counts:
            return {}
        total = sum(counts.values())
        return {
            self.vocabulary_[token]: (count / total) * self.idf_.get(token, 1.0)
            for token, count in counts.items()
        }

    @staticmethod
    def _tokens(value: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", value.lower())
        bigrams = [f"{left}_{right}" for left, right in zip(words, words[1:], strict=False)]
        return words + bigrams


def main() -> None:
    """CLI entrypoint for official-source RAG ingestion."""
    parser = argparse.ArgumentParser(description="Build AML RAG artifacts from official source manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_rag_artifacts(args.manifest, args.artifact_dir), indent=2))


if __name__ == "__main__":
    main()
