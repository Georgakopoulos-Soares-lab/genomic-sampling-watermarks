from __future__ import annotations

import unittest

from genomic_watermarks.metrics import (
    inverse_simpson_support,
    jensen_shannon_divergence_bits,
    normalized_probabilities,
    shannon_entropy_bits,
    top1_mass,
    total_variation_distance,
)


class DistributionMetricsTest(unittest.TestCase):
    def test_probability_normalization(self) -> None:
        self.assertEqual(normalized_probabilities((2, 3)), (0.4, 0.6))
        with self.assertRaises(ValueError):
            normalized_probabilities(())

    def test_basic_distribution_summaries(self) -> None:
        self.assertAlmostEqual(shannon_entropy_bits((0.5, 0.5)), 1.0)
        self.assertAlmostEqual(inverse_simpson_support((0.5, 0.5)), 2.0)
        self.assertAlmostEqual(top1_mass((0.25, 0.75)), 0.75)

    def test_distances_are_zero_for_equal_distributions(self) -> None:
        values = (0.2, 0.3, 0.5)
        self.assertEqual(total_variation_distance(values, values), 0.0)
        self.assertEqual(jensen_shannon_divergence_bits(values, values), 0.0)


if __name__ == "__main__":
    unittest.main()
