"""Categorical goodness-of-fit for distribution-preservation checks.

The declared model law over 4,096 tokens is sparse at realistic sample sizes, so
the asymptotic chi-square reference distribution is unreliable. These helpers use
a parametric Monte Carlo reference instead: resample counts from the declared law
and compare the observed statistic to that simulated null.

A passing test supports one-step marginal preservation at the tested state. It is
not evidence of sequence-level indistinguishability.
"""

from __future__ import annotations

import bisect
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from genomic_watermarks.metrics import normalized_probabilities


@dataclass(frozen=True, slots=True)
class GoodnessOfFitResult:
    """One Monte Carlo goodness-of-fit outcome and the inputs needed to read it."""

    statistic: float
    p_value: float
    draws: int
    categories: int
    support_categories: int
    replicates: int
    seed: int
    replicate_statistic_mean: float
    replicate_statistic_max: float


def observed_counts(tokens: Sequence[str], items: Sequence[str]) -> tuple[int, ...]:
    """Count observed tokens in the declared item order."""

    if not items:
        raise ValueError("items must not be empty")
    index_of = {item: index for index, item in enumerate(items)}
    if len(index_of) != len(items):
        raise ValueError("items must be unique")
    counts = [0] * len(items)
    for token in tokens:
        position = index_of.get(token)
        if position is None:
            raise ValueError("observed a token outside the declared support")
        counts[position] += 1
    return tuple(counts)


def g_statistic(counts: Sequence[int], probabilities: Sequence[float]) -> float:
    """Return the likelihood-ratio (G) statistic against a fully specified law.

    Categories with zero declared probability must also have zero observations;
    otherwise the statistic is undefined and this raises.
    """

    probs = normalized_probabilities(probabilities)
    if len(counts) != len(probs):
        raise ValueError("counts and probabilities must have the same length")
    total = sum(int(count) for count in counts)
    if total <= 0:
        raise ValueError("counts must contain at least one observation")
    terms: list[float] = []
    for count, probability in zip(counts, probs, strict=True):
        observed = int(count)
        if observed < 0:
            raise ValueError("counts must be non-negative")
        if observed == 0:
            continue
        expected = probability * total
        if expected <= 0.0:
            raise ValueError("observed a category with zero declared probability")
        terms.append(observed * math.log(observed / expected))
    return 2.0 * math.fsum(terms)


def _cumulative(probabilities: Sequence[float]) -> list[float]:
    cumulative: list[float] = []
    running = 0.0
    for probability in probabilities:
        running += probability
        cumulative.append(running)
    cumulative[-1] = 1.0
    return cumulative


def _multinomial_counts(
    cumulative: Sequence[float],
    categories: int,
    draws: int,
    rng: random.Random,
) -> list[int]:
    """Draw multinomial counts with one inverse-CDF lookup per observation."""

    counts = [0] * categories
    for _ in range(draws):
        index = bisect.bisect_right(cumulative, rng.random())
        if index >= categories:
            index = categories - 1
        counts[index] += 1
    return counts


def monte_carlo_goodness_of_fit(
    counts: Sequence[int],
    probabilities: Sequence[float],
    *,
    replicates: int,
    seed: int,
) -> GoodnessOfFitResult:
    """Compare the observed G statistic to a parametric Monte Carlo null.

    The p-value uses the conventional ``(1 + exceedances) / (1 + replicates)``
    estimator so it is never exactly zero.
    """

    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    probs = normalized_probabilities(probabilities)
    statistic = g_statistic(counts, probs)
    draws = sum(int(count) for count in counts)
    rng = random.Random(seed)
    cumulative = _cumulative(probs)
    exceedances = 0
    replicate_total = 0.0
    replicate_max = 0.0
    for _ in range(replicates):
        replicate_counts = _multinomial_counts(cumulative, len(probs), draws, rng)
        replicate_statistic = g_statistic(replicate_counts, probs)
        replicate_total += replicate_statistic
        replicate_max = max(replicate_max, replicate_statistic)
        if replicate_statistic >= statistic:
            exceedances += 1
    return GoodnessOfFitResult(
        statistic=statistic,
        p_value=(1 + exceedances) / (1 + replicates),
        draws=draws,
        categories=len(probs),
        support_categories=sum(1 for probability in probs if probability > 0.0),
        replicates=replicates,
        seed=seed,
        replicate_statistic_mean=replicate_total / replicates,
        replicate_statistic_max=replicate_max,
    )


def token_goodness_of_fit(
    tokens: Sequence[str],
    items: Sequence[str],
    probabilities: Sequence[float],
    *,
    replicates: int,
    seed: int,
) -> GoodnessOfFitResult:
    """Run the Monte Carlo goodness-of-fit test directly on sampled tokens."""

    if not tokens:
        raise ValueError("tokens must not be empty")
    return monte_carlo_goodness_of_fit(
        observed_counts(tokens, items),
        probabilities,
        replicates=replicates,
        seed=seed,
    )


def summarize_p_values(p_values: Mapping[str, float], alpha: float = 0.05) -> dict[str, float]:
    """Summarize a family of independent-state p-values without claiming a global test."""

    if not p_values:
        raise ValueError("at least one p-value is required")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    values = [float(value) for value in p_values.values()]
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("p-values must lie in [0, 1]")
    count = len(values)
    rejections = sum(value < alpha for value in values)
    bonferroni_alpha = alpha / count
    return {
        "tests": float(count),
        "alpha": alpha,
        "rejections_at_alpha": float(rejections),
        "rejection_fraction": rejections / count,
        "expected_rejections_under_null": alpha * count,
        "bonferroni_alpha": bonferroni_alpha,
        "rejections_at_bonferroni": float(sum(value < bonferroni_alpha for value in values)),
        "minimum_p_value": min(values),
    }
