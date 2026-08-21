"""Distribution and channel metrics used by E0-E3."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence


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


def partition_mass(
    items: Sequence[str],
    probabilities: Iterable[float],
    partition: Mapping[str, bool],
) -> float:
    probs = normalized_probabilities(probabilities)
    if len(items) != len(probs):
        raise ValueError("items and probabilities must have the same length")
    missing = [item for item in items if item not in partition]
    if missing:
        raise ValueError(f"partition is missing {len(missing)} item(s)")
    return math.fsum(
        probability for item, probability in zip(items, probs, strict=True) if partition[item]
    )


def binary_entropy_bits(probability: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must lie in [0, 1]")
    if probability in {0.0, 1.0}:
        return 0.0
    return -probability * math.log2(probability) - (1.0 - probability) * math.log2(
        1.0 - probability
    )


def maximal_coupling_information_bits(group_one_mass: float) -> float:
    """Mutual information I(C; G) for a fair bit and maximal coupling.

    ``C`` is the fair latent bit and ``G`` is the sampled token's partition
    group. The expression is ``h2(q) - 1/2 h2(|2q-1|)``.
    """

    if not 0.0 <= group_one_mass <= 1.0:
        raise ValueError("group mass must lie in [0, 1]")
    q = group_one_mass
    return binary_entropy_bits(q) - 0.5 * binary_entropy_bits(abs(2.0 * q - 1.0))


def information_bits_per_base(group_one_mass: float, k: int = 6) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    return maximal_coupling_information_bits(group_one_mass) / k
