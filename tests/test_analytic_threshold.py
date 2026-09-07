"""The analytic mean-g threshold, and the reason it replaces an order statistic.

An empirical threshold is an order statistic of the null trials, so with ``n``
trials the smallest attainable false-positive rate is ``1 / n``. A 1% target
taken from 128 trials is therefore roughly the sample maximum, and its sampling
variance -- not the detector -- decides the reported rate. The mean-g null is
known in closed form, so it does not need estimating at all.
"""

from __future__ import annotations

import math
import random
import statistics
import unittest
from statistics import NormalDist

from genomic_watermarks.detector.search import (
    analytic_normal_threshold,
    binomial_standardized_exceedance_probability,
    calibrate_threshold,
)


class AnalyticNormalThresholdTest(unittest.TestCase):
    def test_threshold_is_the_normal_quantile(self) -> None:
        for target in (0.05, 0.01, 0.005, 0.001):
            calibration = analytic_normal_threshold([0.0, 1.0, -1.0], target)
            self.assertAlmostEqual(
                calibration.threshold, NormalDist().inv_cdf(1.0 - target), places=12
            )
            self.assertEqual(calibration.source, "analytic_standard_normal")

    def test_threshold_does_not_depend_on_the_null_sample(self) -> None:
        """The whole point: the number is not estimated from the trials."""

        rng = random.Random(11)
        first = analytic_normal_threshold([rng.gauss(0, 1) for _ in range(32)], 0.01)
        second = analytic_normal_threshold([rng.gauss(0, 1) for _ in range(4096)], 0.01)
        self.assertEqual(first.threshold, second.threshold)

    def test_every_target_is_attainable_unlike_the_order_statistic(self) -> None:
        nulls = [0.0] * 128
        analytic = analytic_normal_threshold(nulls, 0.001)
        empirical = calibrate_threshold(nulls, 0.001)
        self.assertTrue(analytic.is_attainable)
        self.assertEqual(analytic.attainable_false_positive_rate, 0.0)
        self.assertFalse(empirical.is_attainable)
        self.assertAlmostEqual(empirical.attainable_false_positive_rate, 1 / 128)

    def test_achieved_rate_is_a_goodness_of_fit_check(self) -> None:
        """On a true standard normal null the exceedance should track the target."""

        rng = random.Random(2718)
        nulls = [rng.gauss(0.0, 1.0) for _ in range(200_000)]
        calibration = analytic_normal_threshold(nulls, 0.01)
        self.assertAlmostEqual(calibration.achieved_false_positive_rate, 0.01, delta=0.002)

    def test_fit_check_detects_an_overdispersed_null(self) -> None:
        """A null that is not standard normal must show up as a bad achieved rate."""

        rng = random.Random(99)
        nulls = [rng.gauss(0.0, 1.6) for _ in range(200_000)]
        calibration = analytic_normal_threshold(nulls, 0.01)
        self.assertGreater(calibration.achieved_false_positive_rate, 0.03)

    def test_order_statistic_threshold_is_high_variance_at_realistic_trial_counts(self) -> None:
        """Reproduces the defect this function exists to remove.

        With 128 standard-normal trials the empirical 1% threshold scatters
        widely around the true 2.326, which is why a run can calibrate low and
        then miss its target on held-out nulls.
        """

        thresholds = []
        for seed in range(200):
            rng = random.Random(seed)
            nulls = [rng.gauss(0.0, 1.0) for _ in range(128)]
            thresholds.append(calibrate_threshold(nulls, 0.01).threshold)
        spread = statistics.pstdev(thresholds)
        self.assertGreater(spread, 0.15)
        self.assertEqual(
            analytic_normal_threshold([0.0], 0.01).threshold, NormalDist().inv_cdf(0.99)
        )

    def test_rejects_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            analytic_normal_threshold([], 0.01)
        for target in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                analytic_normal_threshold([0.0], target)

    def test_exact_binomial_tail_matches_enumeration(self) -> None:
        for total in (1, 2, 5, 20, 63):
            for threshold in (-1.0, 0.0, 1.25, 3.0):
                enumerated = sum(
                    math.comb(total, ones) / (2**total)
                    for ones in range(total + 1)
                    if (2 * ones - total) / math.sqrt(total) > threshold
                )
                self.assertAlmostEqual(
                    binomial_standardized_exceedance_probability(total, threshold),
                    enumerated,
                    places=13,
                )

    def test_real_detector_lattices_stay_close_to_one_percent(self) -> None:
        threshold = NormalDist().inv_cdf(0.99)
        for total in (1_800, 3_720, 7_560, 15_240):
            exact = binomial_standardized_exceedance_probability(total, threshold)
            self.assertAlmostEqual(exact, 0.01, delta=0.0015)

    def test_exact_binomial_tail_rejects_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            binomial_standardized_exceedance_probability(0, 2.326)
        with self.assertRaises(ValueError):
            binomial_standardized_exceedance_probability(100, float("nan"))
