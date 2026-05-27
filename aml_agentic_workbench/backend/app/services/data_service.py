"""Local AML data access service backed by synthetic sample files."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings


class DataService:
    """Typed facade for AML data access.

    The implementation uses pandas for the local prototype. Callers depend on
    this service interface so the backend can later swap in PySpark, SQL, or a
    governed feature store without changing agent tools.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_sample_data_dir()
        self.real_data_dir = _resolve_repo_path(Path(get_settings().real_data_dir))
        model_artifact_dir = _resolve_repo_path(Path(get_settings().model_artifact_dir))
        self.model_feature_artifact = model_artifact_dir / "customer_features.csv"
        self._customers = self._load_csv("customers.csv")
        self._transactions = self._load_csv("transactions.csv")
        self._features = self._load_csv("customer_features.csv")
        self._model_outputs = self._load_csv("model_outputs.csv")

    def get_transactions(self, customer_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Return transactions for a customer ordered by timestamp."""
        rows = self._transactions[self._transactions["customer_id"] == customer_id].sort_values("timestamp")
        if rows.empty:
            real_rows = self._get_real_transactions(customer_id, limit=limit)
            if real_rows:
                return real_rows
        if limit is not None:
            rows = rows.head(limit)
        return self._records(rows)

    def get_feature_summary(self, customer_id: str) -> dict[str, Any]:
        """Return engineered feature summary for a customer."""
        rows = self._features[self._features["customer_id"] == customer_id]
        if rows.empty:
            real_summary = self._get_real_feature_summary(customer_id)
            if real_summary:
                return real_summary
            raise ValueError(f"No customer_features record found for customer_id '{customer_id}'.")
        row = rows.iloc[0].to_dict()
        result = self._clean_record(row)
        result["top_features"] = self._split_pipe_list(str(result.get("top_features", "")))
        return result

    def get_model_outputs(self, customer_id: str) -> dict[str, Any]:
        """Return model outputs for a customer."""
        row = self._single_row(self._model_outputs, customer_id, "model_outputs")
        result = self._clean_record(row)
        result["top_features"] = self._split_pipe_list(str(result.get("top_features", "")))
        return result

    def get_network_summary(self, customer_id: str) -> dict[str, Any]:
        """Summarize counterparty network concentration for a customer."""
        transactions = self._transactions[self._transactions["customer_id"] == customer_id]
        if transactions.empty:
            real_transactions = pd.DataFrame(self._get_real_transactions(customer_id))
            if real_transactions.empty:
                raise ValueError(f"No transactions found for customer_id '{customer_id}'.")
            country_series = real_transactions.get("country", pd.Series(dtype=str))
            cross_border_series = real_transactions.get("is_cross_border", pd.Series(dtype=int))
            return {
                "transaction_count": int(len(real_transactions)),
                "unique_counterparties": 0,
                "top_counterparty_id": None,
                "top_counterparty_transaction_count": 0,
                "counterparty_concentration_ratio": 0.0,
                "counterparty_countries": country_series.value_counts().to_dict(),
                "cross_border_transaction_count": int(cross_border_series.sum()),
                "cross_border_ratio": round(float(cross_border_series.mean()), 4),
                "total_amount": float(real_transactions["amount"].sum()),
                "average_amount": round(float(real_transactions["amount"].mean()), 2),
            }

        counterparty_counts = transactions["counterparty_id"].value_counts()
        country_counts = transactions["counterparty_country"].value_counts()
        total = int(len(transactions))
        cross_border = int(transactions["is_cross_border"].astype(bool).sum())
        top_counterparty_count = int(counterparty_counts.iloc[0]) if not counterparty_counts.empty else 0
        concentration_ratio = round(top_counterparty_count / total, 4) if total else 0.0

        return {
            "transaction_count": total,
            "unique_counterparties": int(transactions["counterparty_id"].nunique()),
            "top_counterparty_id": str(counterparty_counts.index[0]) if not counterparty_counts.empty else None,
            "top_counterparty_transaction_count": top_counterparty_count,
            "counterparty_concentration_ratio": concentration_ratio,
            "counterparty_countries": country_counts.to_dict(),
            "cross_border_transaction_count": cross_border,
            "cross_border_ratio": round(cross_border / total, 4) if total else 0.0,
            "total_amount": float(transactions["amount"].sum()),
            "average_amount": round(float(transactions["amount"].mean()), 2),
        }

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Sample data file not found: {path}")
        return pd.read_csv(path)

    def _get_real_feature_summary(self, customer_id: str) -> dict[str, Any]:
        if not self.model_feature_artifact.exists():
            return {}
        for chunk in pd.read_csv(self.model_feature_artifact, chunksize=10_000, index_col=0):
            if customer_id in chunk.index:
                row = self._clean_record(chunk.loc[customer_id].to_dict())
                row["customer_id"] = customer_id
                row["top_features"] = []
                return row
        return {}

    def _get_real_transactions(self, customer_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.real_data_dir.exists():
            return []
        from app.ml.features import CHANNELS, normalize_channel_frame

        records: list[dict[str, Any]] = []
        for channel in CHANNELS:
            path = self.real_data_dir / f"{channel}.csv"
            if not path.exists():
                continue
            for chunk in pd.read_csv(path, chunksize=100_000):
                matches = chunk[chunk["customer_id"].astype(str) == customer_id]
                if matches.empty:
                    continue
                normalized = normalize_channel_frame(matches, channel)
                for row in normalized.to_dict(orient="records"):
                    records.append(
                        {
                            "customer_id": row["customer_id"],
                            "transaction_id": row["transaction_id"],
                            "timestamp": str(row["transaction_datetime"]),
                            "amount": row["amount_cad"],
                            "direction": row["direction"],
                            "channel": row["channel"],
                            "counterparty_id": None,
                            "counterparty_country": row["country"],
                            "customer_country": "CA",
                            "currency": "CAD",
                            "is_cross_border": int(row["is_cross_border"]),
                            "risk_score": None,
                            "anomaly_score": None,
                            "top_features": "",
                            "country": row["country"],
                        }
                    )
                    if limit is not None and len(records) >= limit:
                        return records
        records.sort(key=lambda item: str(item["timestamp"]))
        return records[:limit] if limit is not None else records

    @staticmethod
    def _records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        return [DataService._clean_record(row) for row in dataframe.to_dict(orient="records")]

    @staticmethod
    def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in record.items():
            if pd.isna(value):
                clean[key] = None
            elif hasattr(value, "item"):
                clean[key] = value.item()
            else:
                clean[key] = value
        return clean

    @staticmethod
    def _split_pipe_list(value: str) -> list[str]:
        return [item.strip() for item in value.split("|") if item.strip()]

    @staticmethod
    def _single_row(dataframe: pd.DataFrame, customer_id: str, dataset_name: str) -> dict[str, Any]:
        rows = dataframe[dataframe["customer_id"] == customer_id]
        if rows.empty:
            raise ValueError(f"No {dataset_name} record found for customer_id '{customer_id}'.")
        return rows.iloc[0].to_dict()


def default_sample_data_dir() -> Path:
    """Return the backend sample data directory."""
    return Path(__file__).resolve().parents[2] / "data" / "sample"


def _resolve_repo_path(path: Path) -> Path:
    if path.exists():
        return path
    root_candidate = Path(__file__).resolve().parents[4] / path
    return root_candidate if root_candidate.exists() else path


@lru_cache
def get_data_service() -> DataService:
    """Return a cached local data service."""
    return DataService()
