"""Real-data AML feature engineering."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

CHANNELS = ("abm", "card", "cheque", "eft", "emt", "westernunion", "wire")
COUNTRY_HOME = "CA"


@dataclass(frozen=True)
class RealDataPaths:
    """Paths for uploaded real-data CSV inputs."""

    data_dir: Path

    def channel_path(self, channel: str) -> Path:
        """Return a transaction channel CSV path."""
        return self.data_dir / f"{channel}.csv"


@dataclass(frozen=True)
class FeatureDataset:
    """Customer feature matrix and optional evaluation labels."""

    features: pd.DataFrame
    labels: pd.Series


def normalize_channel_frame(frame: pd.DataFrame, channel: str) -> pd.DataFrame:
    """Normalize one channel-specific transaction frame into common AML transaction fields."""
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "transaction_id",
                "customer_id",
                "amount_cad",
                "direction",
                "transaction_datetime",
                "transaction_date",
                "channel",
                "is_cash",
                "is_cross_border",
                "country",
                "province",
                "city",
            ]
        )

    normalized = pd.DataFrame()
    normalized["transaction_id"] = frame["transaction_id"].astype(str)
    normalized["customer_id"] = frame["customer_id"].astype(str)
    normalized["amount_cad"] = pd.to_numeric(frame["amount_cad"], errors="coerce").fillna(0.0).abs()
    normalized["direction"] = frame["debit_credit"].map({"D": "debit", "C": "credit"}).fillna("unknown")
    normalized["transaction_datetime"] = pd.to_datetime(frame["transaction_datetime"], errors="coerce")
    normalized["transaction_date"] = normalized["transaction_datetime"].dt.date
    normalized["channel"] = channel

    cash_indicator = frame.get("cash_indicator")
    if cash_indicator is not None:
        normalized["is_cash"] = cash_indicator.fillna("N").astype(str).str.upper().eq("Y").astype(int)
    else:
        normalized["is_cash"] = 0
    country = frame.get("country")
    if country is not None:
        normalized["country"] = country.fillna(COUNTRY_HOME).astype(str).str.upper()
    else:
        normalized["country"] = COUNTRY_HOME
    normalized["is_cross_border"] = normalized["country"].ne(COUNTRY_HOME).astype(int)
    normalized["province"] = frame.get("province", pd.Series("", index=frame.index)).fillna("").astype(str)
    normalized["city"] = frame.get("city", pd.Series("", index=frame.index)).fillna("").astype(str)
    return normalized


class RealDataFeatureBuilder:
    """Build customer-level AML model features from uploaded channel and KYC files."""

    def __init__(self, paths: RealDataPaths, *, chunksize: int = 100_000) -> None:
        self.paths = paths
        self.chunksize = chunksize

    def build(self) -> FeatureDataset:
        """Build the feature dataset."""
        transactions = self._load_transactions()
        features = self._transaction_features(transactions)
        features = features.join(self._kyc_features(), how="outer").fillna(0.0)
        features = features.sort_index()
        labels = self._load_labels().reindex(features.index)
        return FeatureDataset(features=features.astype(float), labels=labels)

    def _load_transactions(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for channel in CHANNELS:
            path = self.paths.channel_path(channel)
            if not path.exists():
                continue
            for chunk in pd.read_csv(path, chunksize=self.chunksize):
                if not chunk.empty:
                    frames.append(normalize_channel_frame(chunk, channel))
        if not frames:
            return normalize_channel_frame(pd.DataFrame(), "none")
        return pd.concat(frames, ignore_index=True)

    def _transaction_features(self, transactions: pd.DataFrame) -> pd.DataFrame:
        if transactions.empty:
            return pd.DataFrame()

        grouped = transactions.groupby("customer_id", sort=True)
        features = pd.DataFrame(index=grouped.size().index)
        features["txn_count_total"] = grouped.size()
        features["amount_sum_total"] = grouped["amount_cad"].sum()
        features["amount_mean_total"] = grouped["amount_cad"].mean()
        features["amount_max_total"] = grouped["amount_cad"].max()
        features["amount_std_total"] = grouped["amount_cad"].std().fillna(0.0)
        features["debit_amount_sum"] = (
            transactions[transactions["direction"] == "debit"].groupby("customer_id")["amount_cad"].sum()
        )
        features["credit_amount_sum"] = (
            transactions[transactions["direction"] == "credit"].groupby("customer_id")["amount_cad"].sum()
        )
        features[["debit_amount_sum", "credit_amount_sum"]] = features[
            ["debit_amount_sum", "credit_amount_sum"]
        ].fillna(0.0)
        features["debit_credit_amount_ratio"] = features["debit_amount_sum"] / (features["credit_amount_sum"] + 1.0)
        high_value_transactions = transactions[transactions["amount_cad"] >= 10_000]
        features["high_value_txn_count"] = high_value_transactions.groupby("customer_id").size()
        features["cash_txn_ratio"] = grouped["is_cash"].mean()
        features["cross_border_txn_ratio"] = grouped["is_cross_border"].mean()
        features["channel_diversity"] = grouped["channel"].nunique()

        date_span = grouped["transaction_datetime"].agg(["min", "max"])
        features["active_days_span"] = (date_span["max"] - date_span["min"]).dt.days.fillna(0).clip(lower=0)
        max_date = transactions["transaction_datetime"].max()
        features["days_since_last_txn"] = (max_date - date_span["max"]).dt.days.fillna(0).clip(lower=0)

        channel_counts = pd.crosstab(transactions["customer_id"], transactions["channel"])
        for channel in CHANNELS:
            count_col = f"channel_count_{channel}"
            features[count_col] = channel_counts.get(channel, 0)
            features[f"channel_ratio_{channel}"] = features[count_col] / features["txn_count_total"].clip(lower=1)

        return features.fillna(0.0).infer_objects(copy=False)

    def _kyc_features(self) -> pd.DataFrame:
        individual = self._read_optional_csv("kyc_individual.csv")
        small_business = self._read_optional_csv("kyc_smallbusiness.csv")
        frames: list[pd.DataFrame] = []

        if not individual.empty:
            ind = pd.DataFrame(index=individual["customer_id"].astype(str))
            ind["kyc_customer_type_individual"] = 1
            ind["kyc_customer_type_smallbusiness"] = 0
            ind["kyc_income"] = pd.to_numeric(individual.get("income"), errors="coerce").fillna(0.0).to_numpy()
            ind["kyc_sales"] = 0.0
            ind["kyc_employee_count"] = 0.0
            ind["kyc_onboard_age_days"] = self._age_days(individual.get("onboard_date"))
            frames.append(ind)

        if not small_business.empty:
            sb = pd.DataFrame(index=small_business["customer_id"].astype(str))
            sb["kyc_customer_type_individual"] = 0
            sb["kyc_customer_type_smallbusiness"] = 1
            sb["kyc_income"] = 0.0
            sb["kyc_sales"] = pd.to_numeric(small_business.get("sales"), errors="coerce").fillna(0.0).to_numpy()
            employee_count = pd.to_numeric(small_business.get("employee_count"), errors="coerce")
            sb["kyc_employee_count"] = employee_count.fillna(0.0).to_numpy()
            sb["kyc_onboard_age_days"] = self._age_days(small_business.get("onboard_date"))
            frames.append(sb)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames).groupby(level=0).max()

    def _load_labels(self) -> pd.Series:
        labels = self._read_optional_csv("labels.csv")
        if labels.empty:
            return pd.Series(dtype=int, name="label")
        return labels.set_index(labels["customer_id"].astype(str))["label"].astype(int)

    def _read_optional_csv(self, filename: str) -> pd.DataFrame:
        path = self.paths.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    @staticmethod
    def _age_days(values: Any) -> pd.Series:
        dates = pd.to_datetime(values, errors="coerce")
        reference = pd.Timestamp("2025-01-31")
        return (reference - dates).dt.days.fillna(0).clip(lower=0)
