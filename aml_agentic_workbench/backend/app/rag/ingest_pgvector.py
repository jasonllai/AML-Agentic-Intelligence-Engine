"""Offline ingestion command for PostgreSQL/pgvector AML RAG storage."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from app.rag.ingest import _load_source_text
from app.rag.pgvector_store import ensure_pgvector_schema, replace_pgvector_documents
from app.rag.semantic import chunk_document, load_source_manifest
from app.services.database import engine


def ingest_pgvector(manifest: Path, run_id: str | None = None) -> dict[str, int | str]:
    """Download/chunk official sources and replace pgvector RAG tables."""
    sources = load_source_manifest(manifest)
    chunks_by_source = {}
    failures = []
    for source in sources:
        try:
            source_text = _load_source_text(source.local_path, source.url)
        except Exception as exc:
            failures.append({"source_id": source.id, "url": source.url, "error": f"{exc.__class__.__name__}: {exc}"})
            chunks_by_source[source.id] = []
            continue
        chunks_by_source[source.id] = chunk_document(
            source_id=source.id,
            title=source.title,
            organization=source.organization,
            url=source.url,
            document_type=source.document_type,
            jurisdiction=source.jurisdiction,
            topics=source.topics,
            priority=source.priority,
            text=source_text,
        )

    ensure_pgvector_schema(engine)
    resolved_run_id = run_id or f"rag-{uuid4()}"
    counts = replace_pgvector_documents(
        engine=engine,
        sources=sources,
        chunks_by_source=chunks_by_source,
        run_id=resolved_run_id,
        failures=failures,
    )
    return {"run_id": resolved_run_id, **counts}


def main() -> None:
    """CLI entrypoint for pgvector-backed official-source RAG ingestion."""
    parser = argparse.ArgumentParser(description="Ingest official AML RAG sources into PostgreSQL/pgvector.")
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(ingest_pgvector(args.manifest), indent=2))


if __name__ == "__main__":
    main()
