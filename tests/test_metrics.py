from __future__ import annotations

import unittest

from genomic_watermarks.metrics import (
    information_bits_per_base,
    inverse_simpson_support,
    jensen_shannon_divergence_bits,
    maximal_coupling_information_bits,
    partition_mass,
    shannon_entropy_bits,
    top_k_overlap_fraction,
    total_variation_distance,
)


class MetricsTest(unittest.TestCase):
    def test_uniform_binary_metrics(self) -> None:
        probabilities = (0.5, 0.5)
        self.assertAlmostEqual(shannon_entropy_bits(probabilities), 1.0)
        self.assertAlmostEqual(inverse_simpson_support(probabilities), 2.0)
        self.assertAlmostEqual(maximal_coupling_information_bits(0.5), 1.0)
        self.assertAlmostEqual(information_bits_per_base(0.5), 1.0 / 6.0)

    def test_extreme_partition_has_no_channel_information(self) -> None:
        self.assertAlmostEqual(maximal_coupling_information_bits(0.0), 0.0)
        self.assertAlmostEqual(maximal_coupling_information_bits(1.0), 0.0)

    def test_partition_mass_normalizes_input(self) -> None:
        mass = partition_mass(("A", "B"), (8.0, 2.0), {"A": True, "B": False})
        self.assertAlmostEqual(mass, 0.8)

    def test_distribution_comparison_metrics(self) -> None:
        left = (0.5, 0.5, 0.0)
        right = (0.25, 0.5, 0.25)
        self.assertAlmostEqual(total_variation_distance(left, right), 0.25)
        self.assertGreater(jensen_shannon_divergence_bits(left, right), 0.0)
        self.assertAlmostEqual(jensen_shannon_divergence_bits(left, left), 0.0)
        self.assertAlmostEqual(top_k_overlap_fraction(left, right, 2), 1.0)

    def test_distribution_comparison_rejects_invalid_shape_or_k(self) -> None:
        with self.assertRaises(ValueError):
            total_variation_distance((1.0,), (0.5, 0.5))
        with self.assertRaises(ValueError):
            top_k_overlap_fraction((0.5, 0.5), (0.5, 0.5), 3)


if __name__ == "__main__":
    unittest.main()
