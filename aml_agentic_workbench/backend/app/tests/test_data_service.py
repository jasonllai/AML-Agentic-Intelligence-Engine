"""Data service tests."""

import pytest

from app.services.data_service import DataService


def test_data_service_returns_customer_transactions() -> None:
    """Customer transaction retrieval should return only the requested customer."""
    service = DataService()

    transactions = service.get_transactions("CUST003")

    assert len(transactions) == 6
    assert {transaction["customer_id"] for transaction in transactions} == {"CUST003"}
    assert any("velocity_spike" in str(transaction["top_features"]) for transaction in transactions)


def test_data_service_feature_summary_parses_top_features() -> None:
    """Feature summary should expose top features as a typed list."""
    service = DataService()

    summary = service.get_feature_summary("CUST006")

    assert summary["customer_id"] == "CUST006"
    assert summary["round_amount_ratio"] == 1.0
    assert "round_amount_structuring_style" in summary["top_features"]


def test_data_service_network_summary_identifies_concentration() -> None:
    """Network summary should compute counterparty concentration metrics."""
    service = DataService()

    summary = service.get_network_summary("CUST009")

    assert summary["top_counterparty_id"] == "CP080"
    assert summary["counterparty_concentration_ratio"] == 1.0
    assert summary["unique_counterparties"] == 1


def test_data_service_unknown_customer_raises_clear_error() -> None:
    """Missing customer records should raise a clear ValueError."""
    service = DataService()

    with pytest.raises(ValueError, match="No customer_features record"):
        service.get_feature_summary("UNKNOWN")

