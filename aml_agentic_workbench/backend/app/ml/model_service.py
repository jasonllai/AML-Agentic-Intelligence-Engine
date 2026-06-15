"""Loadable AML model scoring service."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

from app.core.config import get_settings
from app.ml.shap_explanations import ModelAgnosticShapExplainer
from app.ml.train_model import (
    FEATURE_SCHEMA_FILENAME,
    MODEL_FILENAME,
    SCALER_FILENAME,
    TRAINING_FEATURES_FILENAME,
    FeatureScaler,
    LocalIsolationForest,
)

torch.set_num_threads(1)


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
        background_frame = (
            self.training_features[feature_names].astype(float)
            if not self.training_features.empty
            else frame[feature_names]
        )
        background_matrix = self.scaler.transform(background_frame)
        raw_anomaly = float(self.model.anomaly_score(matrix).iloc[0])
        anomaly_score = self._normalize_score(raw_anomaly)
        driver_details = self._isolation_driver_details(
            matrix,
            frame.iloc[0],
            feature_names,
            self._build_shap_explainer(background_matrix, feature_names),
        )
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
            "top_features": [driver["feature_name"] for driver in driver_details]
            or self._top_features(frame.iloc[0], feature_names),
            "model_specific_driver_details": driver_details,
            "explanation_metadata": {
                "backend": self.schema["backend"],
                "artifact_dir": str(self.artifact_dir),
                "score_raw": raw_anomaly,
                "alert_threshold": self.schema["alert_threshold"],
                "feature_values": frame.iloc[0].to_dict(),
            },
        }

    def score_population(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Return ranked model scores for the modeled customer population."""
        if self.training_features.empty:
            raise ModelArtifactError("No customer feature matrix found for population scoring.")
        feature_names = self.schema["feature_names"]
        frame = self.training_features[feature_names].astype(float)
        matrix = self.scaler.transform(frame)
        raw_scores = self.model.anomaly_score(matrix).reset_index(drop=True)
        normalized_scores = raw_scores.map(self._normalize_score)
        ranked = pd.DataFrame(
            {
                "customer_id": frame.index.astype(str),
                "risk_score": normalized_scores,
                "anomaly_score": normalized_scores,
                "score_raw": raw_scores,
            }
        ).sort_values("risk_score", ascending=False, kind="mergesort")
        population_size = len(ranked)
        ranked["rank"] = range(1, population_size + 1)
        ranked["score_percentile"] = (population_size - ranked["rank"] + 1) / population_size
        results: list[dict[str, Any]] = []
        top_rows = ranked.head(top_k).to_dict(orient="records")
        shap_explainer = self._build_shap_explainer(matrix, feature_names) if top_rows else None
        for row in top_rows:
            customer_id = str(row["customer_id"])
            risk_score = round(float(row["risk_score"]), 6)
            original_row = frame.loc[customer_id]
            position = int(frame.index.get_loc(customer_id))
            driver_details = self._isolation_driver_details(
                matrix[position : position + 1],
                original_row,
                feature_names,
                shap_explainer,
            )
            if risk_score >= self.schema["alert_threshold"]:
                recommendation = "alert"
            elif risk_score >= 0.5:
                recommendation = "monitor"
            else:
                recommendation = "no_alert"
            results.append(
                {
                    "customer_id": customer_id,
                    "model_version": self.schema["model_version"],
                    "model_family": self.schema["backend"],
                    "risk_score": risk_score,
                    "anomaly_score": risk_score,
                    "reconstruction_error": None,
                    "alert_recommendation": recommendation,
                    "rank": int(row["rank"]),
                    "score_percentile": round(float(row["score_percentile"]), 6),
                    "top_features": [driver["feature_name"] for driver in driver_details]
                    or self._top_features(original_row, feature_names),
                    "model_specific_driver_details": driver_details,
                    "explanation_metadata": {
                        "backend": self.schema["backend"],
                        "artifact_dir": str(self.artifact_dir),
                        "score_raw": float(row["score_raw"]),
                        "alert_threshold": self.schema["alert_threshold"],
                        "feature_values": original_row.to_dict(),
                    },
                }
            )
        return results

    def score_all_models(self, top_k: int = 10) -> dict[str, list[dict[str, Any]]]:
        """Return top candidates from all supported AML anomaly model families."""
        return {
            "isolation_forest": self.score_population(top_k=top_k),
            "autoencoder": self._score_deep_model("autoencoder", top_k=top_k),
            "variational_autoencoder": self._score_deep_model("variational_autoencoder", top_k=top_k),
            "conditional_variational_autoencoder": self._score_deep_model(
                "conditional_variational_autoencoder",
                top_k=top_k,
            ),
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

    def _build_shap_explainer(self, matrix: np.ndarray, feature_names: list[str]) -> ModelAgnosticShapExplainer:
        background = self._shap_background(matrix)
        return ModelAgnosticShapExplainer(
            score_function=self._score_normalized_matrix,
            background_matrix=background,
            feature_names=feature_names,
        )

    def _score_normalized_matrix(self, matrix: np.ndarray) -> np.ndarray:
        raw_scores = self.model.anomaly_score(np.asarray(matrix, dtype=float))
        return np.asarray([self._normalize_score(float(score)) for score in raw_scores], dtype=float)

    @staticmethod
    def _shap_background(matrix: np.ndarray, max_rows: int = 25) -> np.ndarray:
        if len(matrix) <= max_rows:
            return matrix
        indexes = np.linspace(0, len(matrix) - 1, num=max_rows, dtype=int)
        return matrix[indexes]

    def _isolation_driver_details(
        self,
        candidate_matrix: np.ndarray,
        original_row: pd.Series,
        feature_names: list[str],
        shap_explainer: ModelAgnosticShapExplainer,
    ) -> list[dict[str, Any]]:
        means = pd.Series(getattr(self.scaler, "mean_", [0.0] * len(feature_names)), index=feature_names)
        scales = pd.Series(
            getattr(self.scaler, "scale_", [1.0] * len(feature_names)),
            index=feature_names,
        ).replace(0, 1)
        z_scores = ((original_row[feature_names] - means) / scales).to_dict()
        return shap_explainer.explain(
            candidate_matrix=candidate_matrix,
            original_values=original_row[feature_names].to_dict(),
            baselines=means.to_dict(),
            z_scores={name: float(value) for name, value in z_scores.items()},
            max_drivers=5,
        )

    def _score_deep_model(self, family: str, *, top_k: int) -> list[dict[str, Any]]:
        if self.training_features.empty:
            raise ModelArtifactError("No customer feature matrix found for deep-model population scoring.")
        feature_names = self.schema["feature_names"]
        frame = self.training_features[feature_names].astype(float)
        matrix = self.scaler.transform(frame).astype("float32")
        condition_matrix, conditions = self._condition_matrix()
        artifact = self._load_or_train_deep_artifact(family, matrix, condition_matrix)
        scores, contribution_matrix = self._deep_scores(family, artifact, matrix, condition_matrix)
        normalized_scores = _normalize_array(scores)
        threshold = float(np.quantile(normalized_scores, 0.95))
        means = pd.Series(getattr(self.scaler, "mean_", [0.0] * len(feature_names)), index=feature_names)
        scales = pd.Series(
            getattr(self.scaler, "scale_", [1.0] * len(feature_names)),
            index=feature_names,
        ).replace(0, 1)
        explanation_method = _deep_explanation_method(family)
        ranked = pd.DataFrame(
            {
                "customer_id": frame.index.astype(str),
                "risk_score": normalized_scores,
                "score_raw": scores,
            }
        ).sort_values("risk_score", ascending=False, kind="mergesort")
        ranked["rank"] = range(1, len(ranked) + 1)
        ranked["score_percentile"] = (len(ranked) - ranked["rank"] + 1) / len(ranked)

        results: list[dict[str, Any]] = []
        customer_positions = {str(customer_id): index for index, customer_id in enumerate(frame.index.astype(str))}
        for row in ranked.head(top_k).to_dict(orient="records"):
            customer_id = str(row["customer_id"])
            original_row = frame.loc[customer_id]
            position = customer_positions[customer_id]
            contributions = pd.Series(contribution_matrix[position], index=feature_names).sort_values(ascending=False)
            top_features = [name for name, value in contributions.head(5).items() if float(value) > 0]
            risk_score = round(float(row["risk_score"]), 6)
            if risk_score >= threshold:
                recommendation = "alert"
            elif risk_score >= 0.5:
                recommendation = "monitor"
            else:
                recommendation = "no_alert"
            active_condition = conditions[position] if conditions else "not_applicable"
            results.append(
                {
                    "customer_id": customer_id,
                    "model_version": f"{family}_v1",
                    "model_family": family,
                    "risk_score": risk_score,
                    "anomaly_score": risk_score,
                    "reconstruction_error": float(row["score_raw"]),
                    "alert_recommendation": recommendation,
                    "rank": int(row["rank"]),
                    "score_percentile": round(float(row["score_percentile"]), 6),
                    "top_features": top_features,
                    "model_specific_driver_details": [
                        {
                            "feature_name": feature_name,
                            "customer_value": float(original_row[feature_name]),
                            "population_baseline": float(means[feature_name]),
                            "z_score": round(
                                float((original_row[feature_name] - means[feature_name]) / scales[feature_name]),
                                6,
                            ),
                            "contribution": round(float(contributions[feature_name]), 6),
                            "reconstruction_contribution": round(float(contributions[feature_name]), 6),
                            "explanation_method": explanation_method,
                            "explanation": self._driver_explanation(family, feature_name, active_condition),
                        }
                        for feature_name in top_features
                    ],
                    "explanation_metadata": {
                        "backend": family,
                        "artifact_dir": str(self.artifact_dir),
                        "score_raw": float(row["score_raw"]),
                        "alert_threshold": round(threshold, 6),
                        "active_condition": active_condition,
                        "feature_values": {
                            feature_name: float(original_row[feature_name])
                            for feature_name in top_features
                        },
                    },
                }
            )
        return results

    def _load_or_train_deep_artifact(
        self,
        family: str,
        matrix: np.ndarray,
        condition_matrix: np.ndarray,
    ) -> dict[str, Any]:
        path = self.artifact_dir / f"{family}_torch.pt"
        input_dim = matrix.shape[1]
        condition_dim = condition_matrix.shape[1]
        model = _build_deep_model(family, input_dim=input_dim, condition_dim=condition_dim)
        if path.exists():
            payload = torch.load(path, map_location="cpu", weights_only=False)
            if payload.get("input_dim") != input_dim:
                raise ModelArtifactError(f"{family} artifact feature dimension does not match schema.")
            model.load_state_dict(payload["state_dict"])
            return {"model": model.eval(), "metadata": payload}

        payload = _train_deep_model(family, model, matrix, condition_matrix)
        payload["input_dim"] = input_dim
        payload["condition_dim"] = condition_dim
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(payload, path)
        model.load_state_dict(payload["state_dict"])
        return {"model": model.eval(), "metadata": payload}

    def _deep_scores(
        self,
        family: str,
        artifact: dict[str, Any],
        matrix: np.ndarray,
        condition_matrix: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        model = artifact["model"]
        x = torch.as_tensor(matrix, dtype=torch.float32)
        c = torch.as_tensor(condition_matrix, dtype=torch.float32)
        with torch.no_grad():
            if family == "autoencoder":
                reconstruction = model(x)
                contribution = torch.square(x - reconstruction).numpy()
                return contribution.mean(axis=1), contribution
            if family == "conditional_variational_autoencoder":
                reconstruction, mean, log_variance = model(x, c)
            else:
                reconstruction, mean, log_variance = model(x)
            contribution = torch.square(x - reconstruction).numpy()
            kl = -0.5 * torch.sum(1.0 + log_variance - torch.square(mean) - torch.exp(log_variance), dim=1).numpy()
            return contribution.mean(axis=1) + 0.001 * kl, contribution

    def _condition_matrix(self) -> tuple[np.ndarray, list[str]]:
        conditions: list[str] = []
        for _, row in self.training_features.iterrows():
            if float(row.get("kyc_customer_type_smallbusiness", 0.0)) >= 0.5:
                conditions.append("smallbusiness")
            elif float(row.get("kyc_customer_type_individual", 0.0)) >= 0.5:
                conditions.append("individual")
            else:
                conditions.append("unknown")
        mapping = {"individual": 0, "smallbusiness": 1, "unknown": 2}
        matrix = np.zeros((len(conditions), len(mapping)), dtype="float32")
        for index, condition in enumerate(conditions):
            matrix[index, mapping[condition]] = 1.0
        return matrix, conditions

    @staticmethod
    def _driver_explanation(family: str, feature_name: str, active_condition: str) -> str:
        if family == "autoencoder":
            return f"{feature_name} had elevated reconstruction error for the autoencoder."
        if family == "variational_autoencoder":
            return (
                f"{feature_name} contributed to the VAE reconstruction error; the KL term contributes to the "
                "candidate score but is not feature-attributed in this display."
            )
        if family == "conditional_variational_autoencoder":
            return (
                f"{feature_name} contributed to the conditional VAE reconstruction error within the "
                f"{active_condition} peer condition; the KL term contributes to the candidate score but is not "
                "feature-attributed in this display."
            )
        return f"{feature_name} contributed to the model score."

class ModelService:
    """Backend-neutral model service facade."""

    def __init__(self, backend: IsolationForestModelService) -> None:
        self.backend = backend

    def score_customer(self, customer_id: str) -> dict[str, Any]:
        """Score a customer through the configured backend."""
        return self.backend.score_customer(customer_id)

    def score_population(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Score and rank the modeled customer population."""
        return self.backend.score_population(top_k=top_k)

    def score_all_models(self, top_k: int = 10) -> dict[str, list[dict[str, Any]]]:
        """Score and rank the modeled population across all supported model families."""
        return self.backend.score_all_models(top_k=top_k)


class _Autoencoder(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        hidden = max(4, min(32, input_dim))
        bottleneck = max(2, min(8, input_dim // 2 or 2))
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, bottleneck),
            nn.ReLU(),
            nn.Linear(bottleneck, hidden),
            nn.ReLU(),
            nn.Linear(hidden, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class _VariationalAutoencoder(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        hidden = max(4, min(32, input_dim))
        latent = max(2, min(8, input_dim // 2 or 2))
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden), nn.ReLU())
        self.mean = nn.Linear(hidden, latent)
        self.log_variance = nn.Linear(hidden, latent)
        self.decoder = nn.Sequential(nn.Linear(latent, hidden), nn.ReLU(), nn.Linear(hidden, input_dim))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        hidden = self.encoder(x)
        mean = self.mean(hidden)
        log_variance = self.log_variance(hidden).clamp(-6.0, 6.0)
        return self.decoder(mean), mean, log_variance


class _ConditionalVariationalAutoencoder(nn.Module):
    def __init__(self, input_dim: int, condition_dim: int) -> None:
        super().__init__()
        hidden = max(4, min(32, input_dim + condition_dim))
        latent = max(2, min(8, input_dim // 2 or 2))
        self.encoder = nn.Sequential(nn.Linear(input_dim + condition_dim, hidden), nn.ReLU())
        self.mean = nn.Linear(hidden, latent)
        self.log_variance = nn.Linear(hidden, latent)
        self.decoder = nn.Sequential(nn.Linear(latent + condition_dim, hidden), nn.ReLU(), nn.Linear(hidden, input_dim))

    def forward(
        self,
        x: torch.Tensor,
        condition: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        hidden = self.encoder(torch.cat([x, condition], dim=1))
        mean = self.mean(hidden)
        log_variance = self.log_variance(hidden).clamp(-6.0, 6.0)
        return self.decoder(torch.cat([mean, condition], dim=1)), mean, log_variance


def _build_deep_model(family: str, *, input_dim: int, condition_dim: int) -> nn.Module:
    torch.manual_seed(42)
    if family == "autoencoder":
        return _Autoencoder(input_dim)
    if family == "variational_autoencoder":
        return _VariationalAutoencoder(input_dim)
    if family == "conditional_variational_autoencoder":
        return _ConditionalVariationalAutoencoder(input_dim, condition_dim)
    raise ModelArtifactError(f"Unsupported deep model family '{family}'.")


def _train_deep_model(
    family: str,
    model: nn.Module,
    matrix: np.ndarray,
    condition_matrix: np.ndarray,
) -> dict[str, Any]:
    torch.manual_seed(42)
    model.train()
    sample_size = min(len(matrix), 512)
    sample_index = np.linspace(0, len(matrix) - 1, num=sample_size, dtype=int)
    x = torch.as_tensor(matrix[sample_index], dtype=torch.float32)
    c = torch.as_tensor(condition_matrix[sample_index], dtype=torch.float32)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    for _ in range(4):
        optimizer.zero_grad()
        if family == "autoencoder":
            reconstruction = model(x)
            loss = torch.mean(torch.square(x - reconstruction))
        elif family == "conditional_variational_autoencoder":
            reconstruction, mean, log_variance = model(x, c)
            reconstruction_loss = torch.mean(torch.square(x - reconstruction))
            kl = -0.5 * torch.mean(1.0 + log_variance - torch.square(mean) - torch.exp(log_variance))
            loss = reconstruction_loss + 0.001 * kl
        else:
            reconstruction, mean, log_variance = model(x)
            reconstruction_loss = torch.mean(torch.square(x - reconstruction))
            kl = -0.5 * torch.mean(1.0 + log_variance - torch.square(mean) - torch.exp(log_variance))
            loss = reconstruction_loss + 0.001 * kl
        loss.backward()
        optimizer.step()
    return {
        "state_dict": model.state_dict(),
        "training_rows": int(sample_size),
        "training_loss": float(loss.detach().cpu()),
    }


def _normalize_array(values: np.ndarray) -> np.ndarray:
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if maximum <= minimum:
        return np.zeros(len(values), dtype=float)
    return np.clip((values - minimum) / (maximum - minimum), 0.0, 1.0)


def _deep_explanation_method(family: str) -> str:
    if family == "autoencoder":
        return "reconstruction_error"
    if family == "variational_autoencoder":
        return "vae_reconstruction_error"
    if family == "conditional_variational_autoencoder":
        return "conditional_vae_reconstruction_error"
    raise ModelArtifactError(f"Unsupported deep model family '{family}'.")


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
