"""Loadable AML model scoring service."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.ml.train_model import (
    FEATURE_SCHEMA_FILENAME,
    MODEL_FILENAME,
    SCALER_FILENAME,
    TRAINING_FEATURES_FILENAME,
    FeatureScaler,
    LocalIsolationForest,
)


class ModelArtifactError(RuntimeError):
    """Raised when trained model artifacts are unavailable."""


class IsolationForestModelService:
    """Score customers with offline-trained Isolation Forest artifacts."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.schema = self._load_schema()
        self.model = LocalIsolationForest.from_dict(
            json.loads((self.artifact_dir / MODEL_FILENAME).read_text(encoding="utf-8"))
        )
        self.scaler = FeatureScaler.from_dict(
            json.loads((self.artifact_dir / SCALER_FILENAME).read_text(encoding="utf-8"))
        )
        self.training_features = self._load_training_features()

    def score_customer(self, customer_id: str, features: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a stable AML model output envelope for one customer."""
        feature_names = self.schema["feature_names"]
        if features is None:
            if customer_id not in self.training_features.index:
                raise ModelArtifactError(f"No model feature row found for customer_id '{customer_id}'.")
            row = self.training_features.loc[customer_id].to_dict()
        else:
            row = features
        frame = pd.DataFrame([{name: float(row.get(name, 0.0)) for name in feature_names}])
        matrix = self.scaler.transform(frame[feature_names])
        raw_anomaly = float(self.model.anomaly_score(matrix).iloc[0])
        anomaly_score = self._normalize_score(raw_anomaly)
        if anomaly_score >= self.schema["alert_threshold"]:
            recommendation = "alert"
        elif anomaly_score >= 0.5:
            recommendation = "monitor"
        else:
            recommendation = "no_alert"
        return {
            "customer_id": customer_id,
            "model_version": self.schema["model_version"],
            "risk_score": round(anomaly_score, 6),
            "anomaly_score": round(anomaly_score, 6),
            "reconstruction_error": None,
            "alert_recommendation": recommendation,
            "top_features": self._top_features(frame.iloc[0], feature_names),
            "explanation_metadata": {
                "backend": self.schema["backend"],
                "artifact_dir": str(self.artifact_dir),
                "score_raw": raw_anomaly,
                "alert_threshold": self.schema["alert_threshold"],
            },
        }

    def _load_schema(self) -> dict[str, Any]:
        path = self.artifact_dir / FEATURE_SCHEMA_FILENAME
        if not path.exists():
            raise ModelArtifactError(f"Model feature schema not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_training_features(self) -> pd.DataFrame:
        path = self.artifact_dir / TRAINING_FEATURES_FILENAME
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, index_col=0)

    def _normalize_score(self, raw_score: float) -> float:
        min_score = float(self.schema["score_min"])
        max_score = float(self.schema["score_max"])
        if max_score <= min_score:
            return 0.0
        return max(0.0, min(1.0, (raw_score - min_score) / (max_score - min_score)))

    def _top_features(self, row: pd.Series, feature_names: list[str]) -> list[str]:
        means = pd.Series(getattr(self.scaler, "mean_", [0.0] * len(feature_names)), index=feature_names)
        scales = pd.Series(
            getattr(self.scaler, "scale_", [1.0] * len(feature_names)),
            index=feature_names,
        ).replace(0, 1)
        z_scores = ((row[feature_names] - means) / scales).abs().sort_values(ascending=False)
        return [name for name, value in z_scores.head(5).items() if value > 0]

class ModelService:
    """Backend-neutral model service facade."""

    def __init__(self, backend: IsolationForestModelService) -> None:
        self.backend = backend

    def score_customer(self, customer_id: str) -> dict[str, Any]:
        """Score a customer through the configured backend."""
        return self.backend.score_customer(customer_id)


@lru_cache
def get_model_service() -> ModelService | None:
    """Return configured model service, or None when artifacts have not been trained."""
    settings = get_settings()
    artifact_dir = _resolve_artifact_dir(Path(settings.model_artifact_dir))
    try:
        return ModelService(IsolationForestModelService(artifact_dir))
    except (FileNotFoundError, ModelArtifactError, UnicodeDecodeError, json.JSONDecodeError, KeyError):
        return None


def _resolve_artifact_dir(path: Path) -> Path:
    if path.exists():
        return path
    root_candidate = Path(__file__).resolve().parents[4] / path
    return root_candidate if root_candidate.exists() else path
