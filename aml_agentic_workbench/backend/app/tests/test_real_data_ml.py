"""Real-data AML feature and model tests."""

from pathlib import Path

import pandas as pd

from app.ml.features import RealDataFeatureBuilder, RealDataPaths, normalize_channel_frame
from app.ml.model_service import IsolationForestModelService
from app.ml.train_model import train_isolation_forest


def test_normalize_channel_frame_maps_channel_specific_columns() -> None:
    """Channel normalization should preserve AML evidence fields needed downstream."""
    frame = pd.DataFrame(
        [
            {
                "transaction_id": "t1",
                "customer_id": "c1",
                "amount_cad": 125.50,
                "debit_credit": "D",
                "transaction_datetime": "2025-01-02 03:04:05",
                "cash_indicator": "Y",
                "country": "US",
                "province": "NY",
                "city": "New York",
            }
        ]
    )

    normalized = normalize_channel_frame(frame, "abm")

    assert normalized.iloc[0]["channel"] == "abm"
    assert normalized.iloc[0]["direction"] == "debit"
    assert normalized.iloc[0]["is_cash"] == 1
    assert normalized.iloc[0]["is_cross_border"] == 1
    assert normalized.iloc[0]["transaction_date"].isoformat() == "2025-01-02"


def test_feature_builder_uses_transactions_kyc_and_labels(tmp_path: Path) -> None:
    """Feature building should combine transaction behaviour, KYC context, and label evaluation data."""
    data_dir = tmp_path / "real_data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            ["t1", "c1", 100.0, "D", "2025-01-01 00:00:00", "Y", "CA", "ON", "Toronto"],
            ["t2", "c1", 200.0, "C", "2025-01-03 00:00:00", "N", "US", "NY", "New York"],
        ],
        columns=[
            "transaction_id",
            "customer_id",
            "amount_cad",
            "debit_credit",
            "transaction_datetime",
            "cash_indicator",
            "country",
            "province",
            "city",
        ],
    ).to_csv(data_dir / "abm.csv", index=False)
    for channel in ["card", "cheque", "eft", "emt", "westernunion", "wire"]:
        columns = ["transaction_id", "customer_id", "amount_cad", "debit_credit", "transaction_datetime"]
        pd.DataFrame(columns=columns).to_csv(data_dir / f"{channel}.csv", index=False)
    pd.DataFrame(
        [["c1", "CA", "ON", "Toronto", "F", "single", "001", 75000, "1980-01-01", "2020-01-01"]],
        columns=[
            "customer_id",
            "country",
            "province",
            "city",
            "gender",
            "marital_status",
            "occupation_code",
            "income",
            "birth_date",
            "onboard_date",
        ],
    ).to_csv(data_dir / "kyc_individual.csv", index=False)
    pd.DataFrame(
        columns=[
            "customer_id",
            "country",
            "province",
            "city",
            "industry_code",
            "employee_count",
            "sales",
            "established_date",
            "onboard_date",
        ]
    ).to_csv(data_dir / "kyc_smallbusiness.csv", index=False)
    pd.DataFrame([["001", "Engineer"]], columns=["occupation_code", "occupation_title"]).to_csv(
        data_dir / "kyc_occupation_codes.csv", index=False
    )
    pd.DataFrame([["10", "Retail"]], columns=["industry_code", "industry"]).to_csv(
        data_dir / "kyc_industry_codes.csv", index=False
    )
    pd.DataFrame([["c1", 1]], columns=["customer_id", "label"]).to_csv(data_dir / "labels.csv", index=False)

    dataset = RealDataFeatureBuilder(RealDataPaths(data_dir=data_dir)).build()

    row = dataset.features.loc["c1"]
    assert row["txn_count_total"] == 2
    assert row["channel_count_abm"] == 2
    assert row["cross_border_txn_ratio"] == 0.5
    assert row["kyc_customer_type_individual"] == 1
    assert dataset.labels.loc["c1"] == 1


def test_training_artifacts_round_trip_and_score_customer(tmp_path: Path) -> None:
    """Offline training should create loadable artifacts with bounded customer scores."""
    features = pd.DataFrame(
        [
            {"txn_count_total": 2, "amount_sum_total": 100.0, "channel_diversity": 1},
            {"txn_count_total": 20, "amount_sum_total": 9000.0, "channel_diversity": 3},
            {"txn_count_total": 4, "amount_sum_total": 350.0, "channel_diversity": 1},
            {"txn_count_total": 50, "amount_sum_total": 25000.0, "channel_diversity": 4},
        ],
        index=["c1", "c2", "c3", "c4"],
    )
    labels = pd.Series([0, 1, 0, 1], index=features.index, name="label")

    metrics = train_isolation_forest(features, labels, tmp_path)
    service = IsolationForestModelService(tmp_path)
    score = service.score_customer("c2", features.loc["c2"].to_dict())

    assert 0.0 <= metrics["alert_threshold"] <= 1.0
    assert score["model_version"] == "isolation_forest_v1"
    assert 0.0 <= score["risk_score"] <= 1.0
    assert 0.0 <= score["anomaly_score"] <= 1.0
    assert score["top_features"]
    assert score["alert_recommendation"] in {"no_alert", "monitor", "alert"}
