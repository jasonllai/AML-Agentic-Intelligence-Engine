"""Knowledge retriever tests."""

from app.services.knowledge_retriever import LocalKeywordRetriever


def test_keyword_retriever_returns_relevant_documents() -> None:
    """Keyword retrieval should rank relevant AML documents."""
    retriever = LocalKeywordRetriever()

    documents = retriever.search("round amount cash structuring threshold", limit=2)

    assert documents
    assert documents[0].doc_id.startswith("fintrac_financial_entity_indicators:")
    assert documents[0].url
    assert documents[0].score > 0


def test_keyword_retriever_returns_empty_for_empty_query() -> None:
    """Empty queries should return no documents."""
    retriever = LocalKeywordRetriever()

    assert retriever.search("   ") == []
