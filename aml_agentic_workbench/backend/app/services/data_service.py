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

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        real_data_dir: Path | None = None,
        model_feature_artifact: Path | None = None,
    ) -> None:
        self.data_dir = data_dir or default_sample_data_dir()
        self.real_data_dir = real_data_dir or _resolve_repo_path(Path(get_settings().real_data_dir))
        model_artifact_dir = _resolve_repo_path(Path(get_settings().model_artifact_dir))
        self.model_feature_artifact = model_feature_artifact or model_artifact_dir / "customer_features.csv"
        self._customers = self._load_csv("customers.csv")
        self._transactions = self._load_csv("transactions.csv")
        self._features = self._load_csv("customer_features.csv")
        self._model_outputs = self._load_csv("model_outputs.csv")
        self._customer_data_sources = {
            "abm": "transaction",
            "card": "transaction",
            "cheque": "transaction",
            "eft": "transaction",
            "emt": "transaction",
            "westernunion": "transaction",
            "wire": "transaction",
            "kyc_individual": "kyc",
            "kyc_smallbusiness": "kyc",
            "customer_features": "model_context",
        }

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

    def list_customer_data_sources(self) -> list[dict[str, Any]]:
        """Return metadata for customer-data browser sources."""
        sources: list[dict[str, Any]] = []
        for source, source_type in self._customer_data_sources.items():
            path = self._customer_data_source_path(source)
            if not path.exists():
                continue
            columns = list(pd.read_csv(path, nrows=0).columns.astype(str))
            sources.append(
                {
                    "source": source,
                    "label": source.replace("_", " ").title(),
                    "source_type": source_type,
                    "row_count": _count_csv_rows(path),
                    "columns": columns,
                    "customer_search_supported": "customer_id" in columns or source == "customer_features",
                }
            )
        return sources

    def get_customer_data_profile(self, customer_id: str, *, source: str = "all", limit: int = 100) -> dict[str, Any]:
        """Return customer-scoped source records for the data browser."""
        limit = max(1, min(int(limit), 500))
        requested_sources = self._requested_customer_sources(source)
        sections = [
            section
            for item in requested_sources
            if (section := self._customer_data_section(customer_id, item, limit=limit)) is not None
        ]
        summary = self._customer_data_summary(customer_id, sections)
        return {
            "customer_id": customer_id,
            "source": source,
            "limit": limit,
            "summary": summary,
            "sections": sections,
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

    def _requested_customer_sources(self, source: str) -> list[str]:
        if source == "all":
            return list(self._customer_data_sources)
        return [source] if source in self._customer_data_sources else []

    def _customer_data_section(self, customer_id: str, source: str, *, limit: int) -> dict[str, Any] | None:
        path = self._customer_data_source_path(source)
        if not path.exists():
            return None
        if source == "customer_features":
            records, total = self._customer_feature_records(customer_id, limit=limit)
        else:
            records, total = self._customer_csv_records(path, customer_id, limit=limit)
            records = self._enrich_customer_data_records(source, records)
        if total == 0:
            return None
        columns = list(pd.read_csv(path, nrows=0).columns.astype(str))
        if records:
            columns = list(dict.fromkeys([*columns, *records[0].keys()]))
        return {
            "source": source,
            "label": source.replace("_", " ").title(),
            "source_type": self._customer_data_sources[source],
            "row_count": total,
            "returned_count": len(records),
            "columns": columns,
            "records": records,
            "summary": self._source_summary(source, records, total),
            "truncated": total > len(records),
        }

    def _customer_data_source_path(self, source: str) -> Path:
        if source == "customer_features":
            return self.model_feature_artifact
        return self.real_data_dir / f"{source}.csv"

    def _customer_csv_records(self, path: Path, customer_id: str, *, limit: int) -> tuple[list[dict[str, Any]], int]:
        records: list[dict[str, Any]] = []
        total = 0
        for chunk in pd.read_csv(path, chunksize=100_000):
            if "customer_id" not in chunk.columns:
                continue
            matches = chunk[chunk["customer_id"].astype(str) == customer_id]
            if matches.empty:
                continue
            total += len(matches)
            if len(records) < limit:
                records.extend(self._records(matches.head(limit - len(records))))
        return records, total

    def _customer_feature_records(self, customer_id: str, *, limit: int) -> tuple[list[dict[str, Any]], int]:
        if not self.model_feature_artifact.exists():
            return [], 0
        records: list[dict[str, Any]] = []
        total = 0
        for chunk in pd.read_csv(self.model_feature_artifact, chunksize=10_000, index_col=0):
            if customer_id not in chunk.index:
                continue
            row = self._clean_record(chunk.loc[customer_id].to_dict())
            row["customer_id"] = customer_id
            total += 1
            if len(records) < limit:
                records.append(row)
        return records, total

    def _enrich_customer_data_records(self, source: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if source == "kyc_individual":
            occupation_lookup = self._lookup_map("kyc_occupation_codes", "occupation_code", "occupation_title")
            for record in records:
                record["occupation_title"] = occupation_lookup.get(str(record.get("occupation_code")))
        if source == "kyc_smallbusiness":
            industry_lookup = self._lookup_map("kyc_industry_codes", "industry_code", "industry")
            for record in records:
                record["industry"] = industry_lookup.get(str(record.get("industry_code")))
        return records

    def _lookup_map(self, source: str, key: str, value: str) -> dict[str, str]:
        path = self.real_data_dir / f"{source}.csv"
        if not path.exists():
            return {}
        frame = pd.read_csv(path)
        if key not in frame.columns or value not in frame.columns:
            return {}
        return {
            str(row[key]): str(row[value])
            for row in frame[[key, value]].dropna(subset=[key]).to_dict(orient="records")
        }

    def _customer_type_from_kyc(self, customer_id: str) -> str | None:
        if self._customer_exists_in_source("kyc_individual", customer_id):
            return "individual"
        if self._customer_exists_in_source("kyc_smallbusiness", customer_id):
            return "small_business"
        return None

    def _customer_exists_in_source(self, source: str, customer_id: str) -> bool:
        path = self._customer_data_source_path(source)
        if not path.exists():
            return False
        for chunk in pd.read_csv(path, chunksize=100_000, usecols=["customer_id"]):
            if chunk["customer_id"].astype(str).eq(customer_id).any():
                return True
        return False

    @staticmethod
    def _source_summary(source: str, records: list[dict[str, Any]], total: int) -> dict[str, Any]:
        if not records:
            return {"record_count": total}
        if source in {"abm", "card", "cheque", "eft", "emt", "westernunion", "wire"}:
            amounts = [float(record.get("amount_cad") or 0.0) for record in records]
            credit_amount = sum(
                float(record.get("amount_cad") or 0.0)
                for record in records
                if str(record.get("debit_credit")).upper().startswith("C")
            )
            debit_amount = sum(
                float(record.get("amount_cad") or 0.0)
                for record in records
                if str(record.get("debit_credit")).upper().startswith("D")
            )
            dates = sorted(
                str(record.get("transaction_datetime"))
                for record in records
                if record.get("transaction_datetime")
            )
            return {
                "transaction_count": total,
                "returned_transaction_count": len(records),
                "total_amount": round(sum(amounts), 2),
                "credit_amount": round(credit_amount, 2),
                "debit_amount": round(debit_amount, 2),
                "earliest_transaction_date": dates[0] if dates else None,
                "latest_transaction_date": dates[-1] if dates else None,
                "top_countries": _top_counts(records, "country"),
                "top_provinces": _top_counts(records, "province"),
                "top_cities": _top_counts(records, "city"),
            }
        return {"record_count": total}

    def _customer_data_summary(self, customer_id: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
        sources = [section["source"] for section in sections]
        transaction_sections = [section for section in sections if section["source_type"] == "transaction"]
        total_records = sum(int(section["row_count"]) for section in sections)
        return {
            "customer_type": self._customer_type_from_kyc(customer_id),
            "available_sources": sources,
            "transaction_source_count": len(transaction_sections),
            "total_records": total_records,
            "feature_available": "customer_features" in sources,
        }

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


def _count_csv_rows(path: Path) -> int:
    with path.open("rb") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _top_counts(records: list[dict[str, Any]], field: str, limit: int = 5) -> dict[str, int]:
    values: dict[str, int] = {}
    for record in records:
        value = record.get(field)
        if value is None:
            continue
        key = str(value)
        values[key] = values.get(key, 0) + 1
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit])


@lru_cache
def get_data_service() -> DataService:
    """Return a cached local data service."""
    return DataService()
