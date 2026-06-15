"""Customer data workspace API tests."""

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.data_service import DataService


def _write_real_data_fixture(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "transaction_id": "CARD-1",
                "customer_id": "SYNID0100000167",
                "amount_cad": 25.0,
                "debit_credit": "D",
                "transaction_datetime": "2024-11-01 10:00:00",
                "merchant_category": 5812,
                "ecommerce_ind": 1,
                "country": "CA",
                "province": "ON",
                "city": "TORONTO",
            },
            {
                "transaction_id": "CARD-2",
                "customer_id": "SYNID0100000167",
                "amount_cad": 35.0,
                "debit_credit": "D",
                "transaction_datetime": "2024-11-02 10:00:00",
                "merchant_category": 5968,
                "ecommerce_ind": 0,
                "country": "US",
                "province": None,
                "city": "other",
            },
        ]
    ).to_csv(path / "card.csv", index=False)
    pd.DataFrame(
        [
            {
                "transaction_id": "WIRE-1",
                "customer_id": "SYNID0100000167",
                "amount_cad": 1000.0,
                "debit_credit": "C",
                "transaction_datetime": "2024-11-03",
            },
            {
                "transaction_id": "WIRE-2",
                "customer_id": "OTHER",
                "amount_cad": 2000.0,
                "debit_credit": "D",
                "transaction_datetime": "2024-11-04",
            },
        ]
    ).to_csv(path / "wire.csv", index=False)
    pd.DataFrame(
        [
            {
                "customer_id": "SYNID0100000167",
                "country": "CA",
                "province": "ON",
                "city": "TORONTO",
                "gender": "FEMALE",
                "marital_status": "Married",
                "occupation_code": 10010,
                "income": 48886.0,
                "birth_date": "1972-01-30",
                "onboard_date": "2011-09-20",
            }
        ]
    ).to_csv(path / "kyc_individual.csv", index=False)
    pd.DataFrame(
        [
            {
                "customer_id": "SYNID0200000024",
                "country": "CA",
                "province": "ON",
                "city": "BRAMPTON",
                "industry_code": 112,
                "employee_count": 5,
                "sales": 181876.0,
                "established_date": "2022-12-09",
                "onboard_date": "2022-12-26",
            }
        ]
    ).to_csv(path / "kyc_smallbusiness.csv", index=False)
    pd.DataFrame([{"occupation_code": 10010, "occupation_title": "Financial managers"}]).to_csv(
        path / "kyc_occupation_codes.csv",
        index=False,
    )
    pd.DataFrame([{"industry_code": 112, "industry": "Cattle Farms"}]).to_csv(
        path / "kyc_industry_codes.csv",
        index=False,
    )
    pd.DataFrame([{"customer_id": "SYNID0100000167", "label": 1}]).to_csv(path / "labels.csv", index=False)


def test_customer_data_sources_list_real_data_files(tmp_path: Path) -> None:
    """Sources endpoint should expose raw customer data sources without label leakage."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.list_customer_data_sources()

    sources = {source["source"]: source for source in payload}
    assert sources["card"]["source_type"] == "transaction"
    assert sources["card"]["row_count"] == 2
    assert "customer_id" in sources["card"]["columns"]
    assert sources["kyc_individual"]["source_type"] == "kyc"
    assert "labels" not in sources


def test_customer_data_lookup_returns_all_customer_sections(tmp_path: Path) -> None:
    """Customer lookup should combine KYC and transactions without exposing model labels."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.get_customer_data_profile("SYNID0100000167", source="all", limit=10)

    sections = {section["source"]: section for section in payload["sections"]}
    assert payload["customer_id"] == "SYNID0100000167"
    assert sections["kyc_individual"]["records"][0]["occupation_title"] == "Financial managers"
    assert "labels" not in sections
    assert "label" not in payload["summary"]
    assert sections["card"]["summary"]["transaction_count"] == 2
    assert sections["wire"]["summary"]["credit_amount"] == 1000.0
    assert payload["summary"]["total_records"] == 4


def test_customer_data_source_filter_and_limit_marks_truncation(tmp_path: Path) -> None:
    """Source filter should return only requested records and disclose when rows are capped."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.get_customer_data_profile("SYNID0100000167", source="card", limit=1)

    assert [section["source"] for section in payload["sections"]] == ["card"]
    section = payload["sections"][0]
    assert section["returned_count"] == 1
    assert section["row_count"] == 2
    assert section["truncated"] is True
    assert payload["summary"]["customer_type"] == "individual"


def test_customer_data_transaction_filter_uses_kyc_for_customer_type(tmp_path: Path) -> None:
    """KYC membership should identify individual customers even under transaction-only filters."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.get_customer_data_profile("SYNID0100000167", source="wire", limit=10)

    assert [section["source"] for section in payload["sections"]] == ["wire"]
    assert payload["summary"]["customer_type"] == "individual"


def test_customer_data_small_business_joins_industry(tmp_path: Path) -> None:
    """Small-business KYC rows should include industry names when the lookup file is available."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.get_customer_data_profile("SYNID0200000024", source="kyc_smallbusiness", limit=10)

    assert payload["sections"][0]["records"][0]["industry"] == "Cattle Farms"
    assert payload["summary"]["customer_type"] == "small_business"


def test_customer_data_missing_customer_returns_empty_profile(tmp_path: Path) -> None:
    """Missing customers should return a structured empty response instead of raising."""
    _write_real_data_fixture(tmp_path)
    service = DataService(real_data_dir=tmp_path, model_feature_artifact=tmp_path / "missing_features.csv")

    payload = service.get_customer_data_profile("MISSING", source="all", limit=10)

    assert payload["customer_id"] == "MISSING"
    assert payload["sections"] == []
    assert payload["summary"]["total_records"] == 0


def test_customer_data_api_routes_return_sources_and_profile() -> None:
    """FastAPI should expose customer-data sources and customer profile endpoints."""
    client = TestClient(create_app())

    sources_response = client.get("/api/v1/customer-data/sources")
    profile_response = client.get("/api/v1/customer-data/customer/SYNID0200567030?source=wire&limit=5")

    assert sources_response.status_code == 200
    assert any(source["source"] == "wire" for source in sources_response.json()["sources"])
    assert profile_response.status_code == 200
    assert profile_response.json()["customer_id"] == "SYNID0200567030"
