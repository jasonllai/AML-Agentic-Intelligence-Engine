"""Data service tests."""

import pytest

from app.services.data_service import DataService

REAL_CUSTOMER_ID = "SYNID0100000167"


def test_data_service_returns_customer_transactions() -> None:
    """Customer transaction retrieval should return only the requested customer."""
    service = DataService()

    transactions = service.get_transactions(REAL_CUSTOMER_ID)

    assert len(transactions) == 18
    assert {transaction["customer_id"] for transaction in transactions} == {REAL_CUSTOMER_ID}
    assert {transaction["channel"] for transaction in transactions} == {"cheque", "eft"}


def test_data_service_feature_summary_parses_top_features() -> None:
    """Feature summary should come from real model artifacts, not synthetic sample CSVs."""
    service = DataService()

    summary = service.get_feature_summary(REAL_CUSTOMER_ID)

    assert summary["customer_id"] == REAL_CUSTOMER_ID
    assert summary["txn_count_total"] == 18.0
    assert summary["top_features"] == []


def test_data_service_network_summary_identifies_concentration() -> None:
    """Network summary should compute real-data channel and geography metrics."""
    service = DataService()

    summary = service.get_network_summary(REAL_CUSTOMER_ID)

    assert summary["transaction_count"] == 18
    assert summary["top_channel"] == "eft"
    assert summary["channel_counts"]["eft"] == 17
    assert summary["cross_border_transaction_count"] == 0


def test_data_service_unknown_customer_raises_clear_error() -> None:
    """Missing customer records should raise a clear ValueError."""
    service = DataService()

    with pytest.raises(ValueError, match="No customer_features record"):
        service.get_feature_summary("CUST003")


def test_data_service_customer_exists_uses_real_sources_only() -> None:
    """Customer existence should be based on real_data and model artifacts, not sample IDs."""
    service = DataService()

    assert service.customer_exists(REAL_CUSTOMER_ID) is True
    assert service.customer_exists("CUST003") is False
