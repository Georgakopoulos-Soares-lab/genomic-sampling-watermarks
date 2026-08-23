from __future__ import annotations

import unittest

from genomic_watermarks.detector.search import joint_detection_rate_interval


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
