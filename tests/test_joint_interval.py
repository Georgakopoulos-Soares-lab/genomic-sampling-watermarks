from __future__ import annotations

import random
import unittest

from genomic_watermarks.detector.search import (
    calibrate_threshold,
    calibrated_threshold_value,
    joint_detection_rate_interval,
)


class FastThresholdTest(unittest.TestCase):
    def test_fast_threshold_matches_calibration(self) -> None:
        """The bootstrap's order-statistic threshold must equal the scanning one.

        The joint interval recalibrates on every replicate, so it uses an
        O(n log n) threshold instead of the quadratic scan. If the two ever
        disagreed, every recomputed interval in the ledger would be wrong, so the
        equivalence is checked here rather than assumed — including on inputs that
        are entirely ties, where an order-statistic argument is easiest to get
        wrong.
        """

        rng = random.Random(0)
        for trial in range(400):
            count = rng.choice([1, 2, 3, 7, 20, 100, 101, 480])
            style = trial % 4
            if style == 0:
                values = [rng.gauss(0.0, 1.0) for _ in range(count)]
            elif style == 1:
                values = [float(rng.randrange(3)) for _ in range(count)]
            elif style == 2:
                values = [0.0] * count
            else:
                values = [rng.randrange(-2, 3) / 2 for _ in range(count)]
            for target in (0.001, 0.01, 0.05, 0.1, 0.5, 0.9):
                self.assertEqual(
                    calibrate_threshold(values, target).threshold,
                    calibrated_threshold_value(values, target),
                    (count, target, style),
                )

    def test_fast_threshold_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one trial"):
            calibrated_threshold_value([], 0.01)
        with self.assertRaisesRegex(ValueError, "must lie in"):
            calibrated_threshold_value([0.0], 1.0)


class JointIntervalTest(unittest.TestCase):
    def test_a_large_margin_leaves_the_interval_degenerate(self) -> None:
        """When positives are far above every null, threshold noise cannot matter."""

        positives = {f"c{i}": (20.0,) for i in range(8)}
        nulls = [float(v) / 10 for v in range(40)]
        result = joint_detection_rate_interval(positives, nulls, 0.05, replicates=500, seed=1)
        self.assertAlmostEqual(result["detection_rate"], 1.0)
        self.assertAlmostEqual(result["lower"], 1.0)
        self.assertAlmostEqual(result["upper"], 1.0)

    def test_a_thin_margin_widens_the_interval(self) -> None:
        """Positives sitting on top of the null maximum are not reliably detected."""

        nulls = [3.0] * 30 + [3.5] * 8 + [4.0] * 2
        positives = {f"c{i}": (3.5,) for i in range(8)}
        result = joint_detection_rate_interval(positives, nulls, 0.05, replicates=1000, seed=2)
        self.assertLess(result["lower"], 0.9)
        self.assertEqual(result["resamples_the_threshold"], 1.0)

    def test_clusters_are_averaged_not_pooled(self) -> None:
        """A cluster with many trials must not outvote a cluster with few."""

        positives = {"a": (20.0,) * 100, "b": (0.0,), "c": (0.0,), "d": (0.0,)}
        nulls = [1.0] * 40
        result = joint_detection_rate_interval(positives, nulls, 0.05, replicates=200, seed=3)
        self.assertAlmostEqual(result["detection_rate"], 0.25)

    def test_the_interval_does_not_depend_on_null_ordering(self) -> None:
        """Same data, same seed, different pooling order must give the same bounds.

        The pooled nulls come from two families, and a caller can concatenate them
        in either order. If the bounds moved with that choice, two honest
        recomputations of one admitted cell would disagree.
        """

        positives = {f"c{i}": (3.5,) for i in range(8)}
        family_a = [3.0] * 20 + [3.5] * 5
        family_b = [3.5] * 3 + [4.0] * 2
        forward = joint_detection_rate_interval(
            positives, family_a + family_b, 0.05, replicates=400, seed=7
        )
        reversed_order = joint_detection_rate_interval(
            positives, family_b + family_a, 0.05, replicates=400, seed=7
        )
        permuted = family_a + family_b
        random.Random(3).shuffle(permuted)
        shuffled = joint_detection_rate_interval(positives, permuted, 0.05, replicates=400, seed=7)
        for other in (reversed_order, shuffled):
            self.assertEqual(forward["lower"], other["lower"])
            self.assertEqual(forward["upper"], other["upper"])
            self.assertEqual(forward["threshold"], other["threshold"])

    def test_inputs_are_validated(self) -> None:
        positives = {"a": (1.0,), "b": (1.0,)}
        with self.assertRaisesRegex(ValueError, "at least two positive clusters"):
            joint_detection_rate_interval({"a": (1.0,)}, [0.0], 0.05, replicates=10, seed=0)
        with self.assertRaisesRegex(ValueError, "null trials are required"):
            joint_detection_rate_interval(positives, [], 0.05, replicates=10, seed=0)
        with self.assertRaisesRegex(ValueError, "replicates must be positive"):
            joint_detection_rate_interval(positives, [0.0], 0.05, replicates=0, seed=0)
        with self.assertRaisesRegex(ValueError, "seed must be non-negative"):
            joint_detection_rate_interval(positives, [0.0], 0.05, replicates=10, seed=-1)
        with self.assertRaisesRegex(ValueError, "at least one trial"):
            joint_detection_rate_interval(
                {"a": (), "b": (1.0,)}, [0.0], 0.05, replicates=10, seed=0
            )


if __name__ == "__main__":
    unittest.main()
