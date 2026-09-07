"""Statistical threshold helpers retained for the Carbon SynthID validation.

The position-independent verifier itself lives in
``genomic_watermarks.synthid_position_independent``.  This file keeps the
analytic aligned-detector checks used by the completed generation-quality run.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import NormalDist


@dataclass(frozen=True, slots=True)
class Calibration:
    """A threshold and the observed null exceedance rate used to check it."""

    threshold: float
    target_false_positive_rate: float
    achieved_false_positive_rate: float
    null_trials: int
    attainable_false_positive_rate: float
    null_statistics_sorted: tuple[float, ...] = field(repr=False)
    source: str = "empirical_null_order_statistic"

    @property
    def is_attainable(self) -> bool:
        return self.target_false_positive_rate >= self.attainable_false_positive_rate


def calibrate_threshold(
    null_statistics: Sequence[float],
    target_false_positive_rate: float,
) -> Calibration:
    """Choose the smallest observed threshold meeting a strict exceedance target."""

    if not null_statistics:
        raise ValueError("null calibration requires at least one trial")
    if not 0.0 < target_false_positive_rate < 1.0:
        raise ValueError("target false-positive rate must lie in (0, 1)")
    values = sorted(float(value) for value in null_statistics)
    trials = len(values)
    threshold = values[-1]
    achieved = 0.0
    for candidate in values:
        exceedances = sum(value > candidate for value in values)
        if exceedances / trials <= target_false_positive_rate:
            threshold = candidate
            achieved = exceedances / trials
            break
    return Calibration(
        threshold=threshold,
        target_false_positive_rate=target_false_positive_rate,
        achieved_false_positive_rate=achieved,
        null_trials=trials,
        attainable_false_positive_rate=1.0 / trials,
        null_statistics_sorted=tuple(values),
    )


def analytic_normal_threshold(
    null_statistics: Sequence[float],
    target_false_positive_rate: float,
) -> Calibration:
    """Return the normal-theory threshold used by the original aligned check.

    The null rows are a fit check; they do not determine this threshold.  The
    newer position-independent detector instead uses an exact binomial tail and
    corrects for every tested location and length.
    """

    if not null_statistics:
        raise ValueError("null calibration requires at least one trial")
    if not 0.0 < target_false_positive_rate < 1.0:
        raise ValueError("target false-positive rate must lie in (0, 1)")
    values = sorted(float(value) for value in null_statistics)
    threshold = NormalDist().inv_cdf(1.0 - target_false_positive_rate)
    achieved = sum(value > threshold for value in values) / len(values)
    return Calibration(
        threshold=threshold,
        target_false_positive_rate=target_false_positive_rate,
        achieved_false_positive_rate=achieved,
        null_trials=len(values),
        attainable_false_positive_rate=0.0,
        null_statistics_sorted=tuple(values),
        source="analytic_standard_normal",
    )


def binomial_standardized_exceedance_probability(total: int, threshold: float) -> float:
    """Return the exact fair-binomial tail induced by a strict z-score rule."""

    if total <= 0:
        raise ValueError("binomial total must be positive")
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    first_exceedance = math.floor((total + threshold * math.sqrt(total)) / 2.0) + 1
    if first_exceedance <= 0:
        return 1.0
    if first_exceedance > total:
        return 0.0
    log_probability = (
        math.lgamma(total + 1)
        - math.lgamma(first_exceedance + 1)
        - math.lgamma(total - first_exceedance + 1)
        - total * math.log(2.0)
    )
    probability = math.exp(log_probability)
    tail = probability
    for ones in range(first_exceedance, total):
        probability *= (total - ones) / (ones + 1)
        tail += probability
    return min(1.0, max(0.0, tail))


def empirical_p_value(statistic: float, null_statistics: Sequence[float]) -> float:
    """Compare one score with trials produced by the same detector procedure."""

    if not null_statistics:
        raise ValueError("an empirical p-value requires at least one null trial")
    exceedances = sum(float(value) >= statistic for value in null_statistics)
    return (1 + exceedances) / (1 + len(null_statistics))
