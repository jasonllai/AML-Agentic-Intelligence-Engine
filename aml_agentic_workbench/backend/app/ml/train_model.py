"""Offline Isolation Forest training for real AML data."""

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ml.features import RealDataFeatureBuilder, RealDataPaths

MODEL_FILENAME = "aml_isolation_forest.joblib"
SCALER_FILENAME = "feature_scaler.joblib"
FEATURE_SCHEMA_FILENAME = "feature_schema.json"
TRAINING_METRICS_FILENAME = "training_metrics.json"
TRAINING_FEATURES_FILENAME = "customer_features.csv"


def train_isolation_forest(features: pd.DataFrame, labels: pd.Series, artifact_dir: Path) -> dict[str, Any]:
    """Train Isolation Forest and write loadable scoring artifacts."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    feature_names = list(features.columns)
    scaler = FeatureScaler.fit(features[feature_names])
    matrix = scaler.transform(features[feature_names])
    model = LocalIsolationForest(n_trees=100, max_depth=8, sample_size=min(256, len(features)), random_state=42)
    model.fit(matrix)

    raw_anomaly = model.anomaly_score(matrix)
    min_raw = float(raw_anomaly.min())
    max_raw = float(raw_anomaly.max())
    anomaly_scores = _normalize(raw_anomaly, min_raw, max_raw)
    threshold = _calibrated_threshold(anomaly_scores, labels)

    (artifact_dir / MODEL_FILENAME).write_text(json.dumps(model.to_dict()), encoding="utf-8")
    (artifact_dir / SCALER_FILENAME).write_text(json.dumps(scaler.to_dict()), encoding="utf-8")
    features.to_csv(artifact_dir / TRAINING_FEATURES_FILENAME)
    schema = {
        "model_version": "isolation_forest_v1",
        "backend": "isolation_forest",
        "feature_names": feature_names,
        "score_min": min_raw,
        "score_max": max_raw,
        "alert_threshold": threshold,
    }
    (artifact_dir / FEATURE_SCHEMA_FILENAME).write_text(json.dumps(schema, indent=2), encoding="utf-8")
    metrics = {
        "customer_count": int(len(features)),
        "feature_count": int(len(feature_names)),
        "label_count": int(labels.notna().sum()),
        "positive_label_count": int((labels == 1).sum()),
        "alert_threshold": threshold,
        "mean_anomaly_score": float(anomaly_scores.mean()),
    }
    (artifact_dir / TRAINING_METRICS_FILENAME).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def train_from_real_data(data_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    """Build real-data features and train model artifacts."""
    dataset = RealDataFeatureBuilder(RealDataPaths(data_dir=_resolve_data_dir(data_dir))).build()
    return train_isolation_forest(dataset.features, dataset.labels, artifact_dir)


def _calibrated_threshold(anomaly_scores: pd.Series | Any, labels: pd.Series) -> float:
    scores = pd.Series(list(anomaly_scores)).reset_index(drop=True)
    aligned_labels = labels.reset_index(drop=True)
    positive_scores = scores[aligned_labels == 1]
    if not positive_scores.empty:
        return round(float(positive_scores.quantile(0.25)), 6)
    return round(float(scores.quantile(0.95)), 6)


def _normalize(values: Any, min_value: float, max_value: float) -> pd.Series:
    if max_value <= min_value:
        return pd.Series([0.0] * len(values))
    return pd.Series((values - min_value) / (max_value - min_value)).clip(0.0, 1.0)


def _resolve_data_dir(data_dir: Path) -> Path:
    if data_dir.exists():
        return data_dir
    root_candidate = Path(__file__).resolve().parents[4] / data_dir
    if root_candidate.exists():
        return root_candidate
    raise FileNotFoundError(f"Real data directory not found: {data_dir}")


class FeatureScaler:
    """Small serializable standard scaler for numeric feature frames."""

    def __init__(self, mean_: list[float], scale_: list[float], feature_names: list[str]) -> None:
        self.mean_ = mean_
        self.scale_ = scale_
        self.feature_names = feature_names

    @classmethod
    def fit(cls, frame: pd.DataFrame) -> "FeatureScaler":
        means = frame.mean().astype(float)
        scales = frame.std().replace(0, 1).fillna(1).astype(float)
        return cls(means.to_list(), scales.to_list(), list(frame.columns))

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        matrix = frame[self.feature_names].astype(float).to_numpy()
        return (matrix - np.array(self.mean_)) / np.array(self.scale_)

    def to_dict(self) -> dict[str, object]:
        return {"mean": self.mean_, "scale": self.scale_, "feature_names": self.feature_names}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FeatureScaler":
        return cls(
            mean_=[float(value) for value in list(payload["mean"])],
            scale_=[float(value) for value in list(payload["scale"])],
            feature_names=[str(value) for value in list(payload["feature_names"])],
        )


class LocalIsolationForest:
    """Dependency-light Isolation Forest implementation for offline AML scoring."""

    def __init__(self, *, n_trees: int, max_depth: int, sample_size: int, random_state: int) -> None:
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.sample_size = sample_size
        self.random_state = random_state
        self.trees: list[dict[str, Any]] = []

    def fit(self, matrix: np.ndarray) -> None:
        rng = random.Random(self.random_state)
        rows = list(range(len(matrix)))
        self.trees = []
        for _ in range(self.n_trees):
            sample = rng.sample(rows, min(self.sample_size, len(rows))) if rows else []
            self.trees.append(self._build_tree(matrix, sample, depth=0, rng=rng))

    def anomaly_score(self, matrix: np.ndarray) -> pd.Series:
        if not self.trees:
            return pd.Series([0.0] * len(matrix))
        path_lengths = []
        for row in matrix:
            lengths = [self._path_length(tree, row, depth=0) for tree in self.trees]
            path_lengths.append(float(np.mean(lengths)))
        max_depth = max(1, self.max_depth)
        return pd.Series([1.0 - min(length / max_depth, 1.0) for length in path_lengths])

    def _build_tree(self, matrix: np.ndarray, indexes: list[int], *, depth: int, rng: random.Random) -> dict[str, Any]:
        if depth >= self.max_depth or len(indexes) <= 1:
            return {"leaf": True, "size": len(indexes)}
        feature_count = matrix.shape[1]
        candidate_features = list(range(feature_count))
        rng.shuffle(candidate_features)
        for feature in candidate_features:
            values = matrix[indexes, feature]
            minimum = float(values.min())
            maximum = float(values.max())
            if minimum == maximum:
                continue
            split = rng.uniform(minimum, maximum)
            left = [index for index in indexes if matrix[index, feature] < split]
            right = [index for index in indexes if matrix[index, feature] >= split]
            if left and right:
                return {
                    "leaf": False,
                    "feature": feature,
                    "split": split,
                    "left": self._build_tree(matrix, left, depth=depth + 1, rng=rng),
                    "right": self._build_tree(matrix, right, depth=depth + 1, rng=rng),
                }
        return {"leaf": True, "size": len(indexes)}

    def _path_length(self, tree: dict[str, Any], row: np.ndarray, *, depth: int) -> int:
        if tree.get("leaf") or depth >= self.max_depth:
            return depth
        branch = "left" if row[int(tree["feature"])] < float(tree["split"]) else "right"
        return self._path_length(tree[branch], row, depth=depth + 1)

    def to_dict(self) -> dict[str, object]:
        return {
            "n_trees": self.n_trees,
            "max_depth": self.max_depth,
            "sample_size": self.sample_size,
            "random_state": self.random_state,
            "trees": self.trees,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LocalIsolationForest":
        model = cls(
            n_trees=int(payload["n_trees"]),
            max_depth=int(payload["max_depth"]),
            sample_size=int(payload["sample_size"]),
            random_state=int(payload["random_state"]),
        )
        model.trees = list(payload["trees"])
        return model


def main() -> None:
    """CLI entrypoint for offline training."""
    parser = argparse.ArgumentParser(description="Train AML Isolation Forest artifacts from real_data CSV files.")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    metrics = train_from_real_data(args.data_dir, args.artifact_dir)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
