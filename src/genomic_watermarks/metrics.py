"""Distribution metrics used by the Carbon SynthID validation."""

from __future__ import annotations

import math
from collections.abc import Iterable


def normalized_probabilities(probabilities: Iterable[float]) -> tuple[float, ...]:
    values = tuple(float(value) for value in probabilities)
    if not values:
        raise ValueError("probability vector must not be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("probabilities must be finite and non-negative")
    total = math.fsum(values)
    if total <= 0.0:
        raise ValueError("probability vector must have positive mass")
    return tuple(value / total for value in values)


def shannon_entropy_bits(probabilities: Iterable[float]) -> float:
    probs = normalized_probabilities(probabilities)
    return -math.fsum(probability * math.log2(probability) for probability in probs if probability)


def inverse_simpson_support(probabilities: Iterable[float]) -> float:
    probs = normalized_probabilities(probabilities)
    return 1.0 / math.fsum(probability * probability for probability in probs)


def top1_mass(probabilities: Iterable[float]) -> float:
    return max(normalized_probabilities(probabilities))


def total_variation_distance(
    left: Iterable[float],
    right: Iterable[float],
) -> float:
    """Return total variation distance between two categorical distributions."""

    left_probs = normalized_probabilities(left)
    right_probs = normalized_probabilities(right)
    if len(left_probs) != len(right_probs):
        raise ValueError("probability vectors must have the same length")
    return 0.5 * math.fsum(
        abs(left_value - right_value)
        for left_value, right_value in zip(left_probs, right_probs, strict=True)
    )


def jensen_shannon_divergence_bits(
    left: Iterable[float],
    right: Iterable[float],
) -> float:
    """Return the finite, symmetric Jensen-Shannon divergence in bits."""

    left_probs = normalized_probabilities(left)
    right_probs = normalized_probabilities(right)
    if len(left_probs) != len(right_probs):
        raise ValueError("probability vectors must have the same length")
    midpoint = tuple(
        0.5 * (left_value + right_value)
        for left_value, right_value in zip(left_probs, right_probs, strict=True)
    )

    def divergence(values: tuple[float, ...]) -> float:
        return math.fsum(
            value * math.log2(value / center)
            for value, center in zip(values, midpoint, strict=True)
            if value
        )

    return 0.5 * (divergence(left_probs) + divergence(right_probs))


def top_k_overlap_fraction(
    left: Iterable[float],
    right: Iterable[float],
    k: int,
) -> float:
    """Return the fraction of indices shared by the two top-k sets."""

    left_probs = normalized_probabilities(left)
    right_probs = normalized_probabilities(right)
    if len(left_probs) != len(right_probs):
        raise ValueError("probability vectors must have the same length")
    if not 0 < k <= len(left_probs):
        raise ValueError("k must lie between one and the distribution size")
    left_ranked = sorted(range(len(left_probs)), key=lambda index: (-left_probs[index], index))
    right_ranked = sorted(range(len(right_probs)), key=lambda index: (-right_probs[index], index))
    return len(set(left_ranked[:k]).intersection(right_ranked[:k])) / k
