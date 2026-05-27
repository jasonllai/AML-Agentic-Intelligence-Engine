"""Semantic AML RAG ingestion and retrieval tests."""

from pathlib import Path

from app.rag.ingest import build_rag_artifacts
from app.rag.semantic import chunk_document, load_source_manifest
from app.services.knowledge_retriever import SemanticKnowledgeRetriever


def test_source_manifest_parses_official_metadata(tmp_path: Path) -> None:
    """Source manifests should preserve official-source governance metadata."""
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        """
sources:
  - id: fintrac_indicators
    title: FINTRAC ML/TF indicators
    organization: FINTRAC
    url: https://fintrac-canafe.canada.ca/example
    document_type: regulatory_guidance
    jurisdiction: CA
    priority: 1
    topics: [indicators, suspicious_transactions]
""".strip(),
        encoding="utf-8",
    )

    sources = load_source_manifest(manifest)

    assert sources[0].id == "fintrac_indicators"
    assert sources[0].organization == "FINTRAC"
    assert sources[0].topics == ["indicators", "suspicious_transactions"]


def test_chunk_document_preserves_heading_metadata_and_overlap() -> None:
    """Chunking should keep citation metadata and overlap terms across section boundaries."""
    text = (
        "# Overview\n"
        "Indicators are red flags that require context before suspicion is formed. "
        "Transactions should be assessed with customer knowledge and facts.\n\n"
        "## Wires\n"
        "Repeated wires to new counterparties may warrant review. "
        "Risk indicators are non-conclusive and require human assessment."
    )

    chunks = chunk_document(
        source_id="fintrac_indicators",
        title="FINTRAC indicators",
        organization="FINTRAC",
        url="https://example.test",
        document_type="guidance",
        jurisdiction="CA",
        topics=["indicators"],
        priority=1,
        text=text,
        max_tokens=12,
        overlap_tokens=4,
    )

    assert len(chunks) > 1
    assert chunks[0].metadata["organization"] == "FINTRAC"
    assert chunks[0].section == "Overview"
    assert chunks[1].text.split()[:4] == chunks[0].text.split()[-4:]


def test_semantic_retriever_returns_citation_ready_chunks(tmp_path: Path) -> None:
    """Semantic retrieval should return source URLs and metadata for citation-backed typology mapping."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "fintrac_indicators.md").write_text(
        "# Indicators\nRapid transaction velocity with new counterparties may suggest unusual behaviour.",
        encoding="utf-8",
    )
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        f"""
sources:
  - id: fintrac_indicators
    title: FINTRAC ML/TF indicators
    organization: FINTRAC
    url: https://fintrac-canafe.canada.ca/example
    document_type: regulatory_guidance
    jurisdiction: CA
    priority: 1
    topics: [velocity, counterparties]
    local_path: {docs_dir / "fintrac_indicators.md"}
""".strip(),
        encoding="utf-8",
    )
    artifact_dir = tmp_path / "rag"

    build_rag_artifacts(manifest, artifact_dir)
    results = SemanticKnowledgeRetriever(artifact_dir).search("velocity new counterparties", limit=1)

    assert results
    assert results[0].url == "https://fintrac-canafe.canada.ca/example"
    assert results[0].metadata["organization"] == "FINTRAC"
    assert results[0].score > 0
