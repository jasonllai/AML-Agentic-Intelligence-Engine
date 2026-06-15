"""Mathematical helpers for AML anomaly model families."""

from typing import Any

import numpy as np


class AutoencoderMath:
    """Objective helpers for reconstruction-error anomaly scoring."""

    @staticmethod
    def reconstruction_error(original: Any, reconstruction: Any) -> np.ndarray:
        """Return row-wise mean squared reconstruction error."""
        original_matrix = np.asarray(original, dtype=float)
        reconstructed_matrix = np.asarray(reconstruction, dtype=float)
        if original_matrix.shape != reconstructed_matrix.shape:
            raise ValueError("Autoencoder reconstruction shape must match original feature shape.")
        if original_matrix.ndim == 1:
            original_matrix = original_matrix.reshape(1, -1)
            reconstructed_matrix = reconstructed_matrix.reshape(1, -1)
        return np.mean(np.square(original_matrix - reconstructed_matrix), axis=1)


class VariationalAutoencoderMath:
    """Objective helpers for VAE negative-ELBO anomaly scoring."""

    @staticmethod
    def kl_divergence_standard_normal(mean: Any, log_variance: Any) -> np.ndarray:
        """Return row-wise KL divergence from q(z|x) to a standard normal prior."""
        mean_matrix = np.asarray(mean, dtype=float)
        log_variance_matrix = np.asarray(log_variance, dtype=float)
        if mean_matrix.shape != log_variance_matrix.shape:
            raise ValueError("VAE latent mean and log-variance shapes must match.")
        if mean_matrix.ndim == 1:
            mean_matrix = mean_matrix.reshape(1, -1)
            log_variance_matrix = log_variance_matrix.reshape(1, -1)
        return -0.5 * np.sum(1.0 + log_variance_matrix - np.square(mean_matrix) - np.exp(log_variance_matrix), axis=1)

    @staticmethod
    def negative_elbo(reconstruction_error: Any, kl_divergence: Any, *, beta: float = 1.0) -> np.ndarray:
        """Return reconstruction error plus weighted KL divergence."""
        reconstruction = np.asarray(reconstruction_error, dtype=float)
        kl = np.asarray(kl_divergence, dtype=float)
        if reconstruction.shape != kl.shape:
            raise ValueError("VAE reconstruction and KL arrays must have the same shape.")
        if beta < 0:
            raise ValueError("VAE beta must be non-negative.")
        return reconstruction + beta * kl


class ConditionalVariationalAutoencoderMath:
    """Condition encoding and peer-baseline scoring helpers for CVAE-style models."""

    def __init__(self, conditions: list[str]) -> None:
        if not conditions:
            raise ValueError("CVAE conditions must not be empty.")
        self.conditions = list(conditions)

    def encode_condition(self, condition: str) -> np.ndarray:
        """Return a deterministic one-hot condition vector."""
        if condition not in self.conditions:
            raise ValueError(f"Unknown CVAE condition '{condition}'.")
        encoded = np.zeros(len(self.conditions), dtype=float)
        encoded[self.conditions.index(condition)] = 1.0
        return encoded

    def condition_adjusted_score(
        self,
        reconstruction_score: Any,
        condition_vector: Any,
        condition_baselines: dict[str, float],
    ) -> np.ndarray:
        """Return score above the baseline for the active condition."""
        vector = np.asarray(condition_vector, dtype=float)
        if vector.shape != (len(self.conditions),):
            raise ValueError("Condition vector does not match configured CVAE conditions.")
        active_indexes = np.flatnonzero(vector == 1.0)
        if len(active_indexes) != 1:
            raise ValueError("Condition vector must have exactly one active condition.")
        condition = self.conditions[int(active_indexes[0])]
        if condition not in condition_baselines:
            raise ValueError(f"Missing CVAE baseline for condition '{condition}'.")
        return np.asarray(reconstruction_score, dtype=float) - float(condition_baselines[condition])

