"""Mathematical validity tests for AML anomaly model families."""

import numpy as np
import pytest

from app.ml.anomaly_math import (
    AutoencoderMath,
    ConditionalVariationalAutoencoderMath,
    VariationalAutoencoderMath,
)
from app.ml.train_model import LocalIsolationForest


def test_isolation_forest_scores_isolated_outlier_higher_than_dense_cluster() -> None:
    """Shorter isolation paths should translate into higher anomaly scores for isolated points."""
    matrix = np.array(
        [
            [0.0, 0.0],
            [0.1, 0.0],
            [0.0, 0.1],
            [0.1, 0.1],
            [8.0, 8.0],
        ]
    )
    model = LocalIsolationForest(n_trees=50, max_depth=6, sample_size=5, random_state=7)
    model.fit(matrix)

    scores = model.anomaly_score(matrix)

    assert scores.iloc[-1] > scores.iloc[:4].mean()


def test_autoencoder_reconstruction_error_is_zero_for_perfect_reconstruction() -> None:
    """Autoencoder anomaly scores should be grounded in non-negative reconstruction error."""
    original = np.array([[1.0, 2.0], [3.0, 4.0]])

    error = AutoencoderMath.reconstruction_error(original, original)

    assert error.tolist() == [0.0, 0.0]


def test_autoencoder_scores_outlier_reconstruction_higher_than_normal() -> None:
    """Poor reconstruction should produce a higher anomaly score than near-perfect reconstruction."""
    normal = np.array([[1.0, 1.0]])
    normal_reconstruction = np.array([[1.1, 0.9]])
    outlier_reconstruction = np.array([[5.0, -3.0]])

    normal_error = AutoencoderMath.reconstruction_error(normal, normal_reconstruction).item()
    outlier_error = AutoencoderMath.reconstruction_error(normal, outlier_reconstruction).item()

    assert outlier_error > normal_error


def test_vae_kl_divergence_is_non_negative_and_zero_for_unit_gaussian() -> None:
    """VAE KL divergence should match the closed-form normal-prior term."""
    mean = np.array([[0.0, 0.0]])
    log_variance = np.array([[0.0, 0.0]])

    kl = VariationalAutoencoderMath.kl_divergence_standard_normal(mean, log_variance)

    assert kl.item() == 0.0


def test_vae_loss_combines_reconstruction_and_kl_terms() -> None:
    """VAE anomaly scoring must expose the documented reconstruction plus KL objective."""
    reconstruction = np.array([0.25])
    kl = np.array([0.75])

    loss = VariationalAutoencoderMath.negative_elbo(reconstruction, kl, beta=0.5)

    assert loss.item() == 0.625


def test_cvae_condition_encoding_and_score_are_condition_aware() -> None:
    """CVAE scoring should compare behavior within an explicit encoded condition."""
    encoder = ConditionalVariationalAutoencoderMath(["individual", "small_business"])
    condition = encoder.encode_condition("small_business")

    score = encoder.condition_adjusted_score(np.array([0.7]), condition, {"small_business": 0.2})

    assert condition.tolist() == [0.0, 1.0]
    assert score.item() == pytest.approx(0.5)
