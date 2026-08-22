from __future__ import annotations

import random
import unittest

from genomic_watermarks.dna import BASES
from genomic_watermarks.sequence_proxies import (
    PROXY_METRICS,
    exact_sign_flip_test,
    homopolymer_runs,
    key_averaged_proxy_comparison,
    kmer_counts,
    kmer_distribution,
    kmer_divergence_bits,
    paired_proxy_comparison,
    proxy_metrics,
    symmetric_averaged_proxy_comparison,
)


def random_dna(seed: int, length: int, weights: tuple[float, ...] | None = None) -> str:
    rng = random.Random(seed)
    population = tuple(BASES)
    return "".join(rng.choices(population, weights=weights, k=length))


class KmerTest(unittest.TestCase):
    def test_counts_cover_the_full_alphabet_and_sum_correctly(self) -> None:
        counts = kmer_counts("ATCGGC", 2)
        self.assertEqual(len(counts), 16)
        self.assertEqual(sum(counts.values()), 5)
        self.assertEqual(counts["AT"], 1)
        self.assertEqual(counts["GG"], 1)

    def test_distribution_is_normalized_and_ordered(self) -> None:
        distribution = kmer_distribution("ATCGGC" * 4, 1)
        self.assertEqual(len(distribution), 4)
        self.assertAlmostEqual(sum(distribution), 1.0)

    def test_counts_validate_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            kmer_counts("ATCGGC", 0)
        with self.assertRaisesRegex(ValueError, "shorter than k"):
            kmer_counts("AT", 3)

    def test_divergence_is_zero_for_identical_sequences(self) -> None:
        sequence = random_dna(1, 600)
        self.assertAlmostEqual(kmer_divergence_bits(sequence, sequence, 3), 0.0)

    def test_divergence_grows_for_a_skewed_sequence(self) -> None:
        balanced = random_dna(2, 1200)
        skewed = random_dna(3, 1200, weights=(0.7, 0.1, 0.1, 0.1))
        self.assertGreater(kmer_divergence_bits(balanced, skewed, 1), 0.05)


class HomopolymerTest(unittest.TestCase):
    def test_runs_are_maximal_and_cover_the_sequence(self) -> None:
        self.assertEqual(homopolymer_runs("AAATTCG"), (3, 2, 1, 1))
        self.assertEqual(sum(homopolymer_runs("AAATTCG")), 7)
        self.assertEqual(homopolymer_runs("A"), (1,))

    def test_empty_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            homopolymer_runs("")


class ProxyMetricTest(unittest.TestCase):
    def test_every_declared_metric_is_produced_and_bounded(self) -> None:
        metrics = proxy_metrics(random_dna(4, 3072))
        self.assertEqual(set(metrics), set(PROXY_METRICS))
        self.assertTrue(0.0 <= metrics["gc_fraction"] <= 1.0)
        self.assertTrue(0.0 <= metrics["purine_fraction"] <= 1.0)
        self.assertTrue(0.0 <= metrics["distinct_hexamer_fraction"] <= 1.0)
        self.assertTrue(0.0 <= metrics["cpg_fraction"] <= 1.0)
        self.assertTrue(0.0 <= metrics["base_entropy_bits"] <= 2.0)
        self.assertTrue(0.0 <= metrics["dinucleotide_entropy_bits"] <= 4.0)
        self.assertTrue(0.0 <= metrics["trinucleotide_entropy_bits"] <= 6.0)
        self.assertGreaterEqual(metrics["longest_homopolymer_run"], 1.0)
        self.assertGreaterEqual(metrics["mean_homopolymer_run"], 1.0)

    def test_known_extremes(self) -> None:
        homopolymer = proxy_metrics("A" * 600)
        self.assertAlmostEqual(homopolymer["gc_fraction"], 0.0)
        self.assertAlmostEqual(homopolymer["base_entropy_bits"], 0.0)
        self.assertAlmostEqual(homopolymer["longest_homopolymer_run"], 600.0)
        self.assertAlmostEqual(homopolymer["distinct_hexamer_fraction"], 1.0 / 595.0)

        alternating = proxy_metrics("GC" * 300)
        self.assertAlmostEqual(alternating["gc_fraction"], 1.0)
        self.assertAlmostEqual(alternating["mean_homopolymer_run"], 1.0)

    def test_short_sequences_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least six bases"):
            proxy_metrics("ATCG")


class ExactSignFlipTest(unittest.TestCase):
    def test_all_zero_differences_give_a_p_value_of_one(self) -> None:
        result = exact_sign_flip_test([0.0] * 8)
        self.assertAlmostEqual(result["p_value"], 1.0)
        self.assertAlmostEqual(result["mean_difference"], 0.0)
        self.assertEqual(result["permutations"], 256.0)
        self.assertEqual(result["pairs"], 8.0)

    def test_consistent_large_differences_hit_the_permutation_floor(self) -> None:
        result = exact_sign_flip_test([1.0, 1.1, 0.9, 1.2, 1.05, 0.95, 1.15, 1.0])
        self.assertAlmostEqual(result["p_value"], 2.0 / 256.0)
        self.assertGreater(result["mean_difference"], 0.9)

    def test_mixed_signs_are_not_significant(self) -> None:
        result = exact_sign_flip_test([0.4, -0.5, 0.3, -0.2, 0.1, -0.35, 0.25, -0.15])
        self.assertGreater(result["p_value"], 0.2)

    def test_the_test_validates_its_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two pairs"):
            exact_sign_flip_test([1.0])
        with self.assertRaisesRegex(ValueError, "limited to 20 pairs"):
            exact_sign_flip_test([1.0] * 21)
        with self.assertRaisesRegex(ValueError, "must be finite"):
            exact_sign_flip_test([1.0, float("nan")])


class PairedComparisonTest(unittest.TestCase):
    def test_matched_random_arms_are_not_flagged(self) -> None:
        watermarked = {f"case_{index}": random_dna(100 + index, 3072) for index in range(8)}
        ordinary = {f"case_{index}": random_dna(200 + index, 3072) for index in range(8)}
        comparison = paired_proxy_comparison(watermarked, ordinary)
        self.assertEqual(set(comparison), set(PROXY_METRICS))
        rejections = sum(comparison[metric]["p_value"] < 0.05 for metric in PROXY_METRICS)
        self.assertLessEqual(rejections, 1)

    def test_a_systematically_skewed_arm_is_flagged(self) -> None:
        watermarked = {
            f"case_{index}": random_dna(300 + index, 3072, weights=(0.55, 0.15, 0.15, 0.15))
            for index in range(8)
        }
        ordinary = {f"case_{index}": random_dna(400 + index, 3072) for index in range(8)}
        comparison = paired_proxy_comparison(watermarked, ordinary)
        self.assertLess(comparison["base_entropy_bits"]["p_value"], 0.01)
        self.assertLess(comparison["purine_fraction"]["p_value"], 0.01)

    def test_key_averaging_reports_spread_and_validates_inputs(self) -> None:
        ordinary = {f"case_{i}": random_dna(700 + i, 1200) for i in range(4)}
        by_key = {
            f"key_{k}": {f"case_{i}": random_dna(800 + 10 * k + i, 1200) for i in range(4)}
            for k in range(3)
        }
        comparison = key_averaged_proxy_comparison(by_key, ordinary)
        self.assertEqual(set(comparison), set(PROXY_METRICS))
        for metric in PROXY_METRICS:
            self.assertEqual(comparison[metric]["keys"], 3.0)
            self.assertGreaterEqual(comparison[metric]["mean_within_prompt_spread_over_keys"], 0.0)
        with self.assertRaisesRegex(ValueError, "at least two keys"):
            key_averaged_proxy_comparison({"key_0": by_key["key_0"]}, ordinary)
        with self.assertRaisesRegex(ValueError, "same prompts as the control"):
            key_averaged_proxy_comparison(
                {"key_0": by_key["key_0"], "key_1": {"case_0": random_dna(1, 1200)}}, ordinary
            )

    def test_key_averaging_flags_a_systematic_shift(self) -> None:
        ordinary = {f"case_{i}": random_dna(900 + i, 1800) for i in range(6)}
        by_key = {
            f"key_{k}": {
                f"case_{i}": random_dna(1000 + 10 * k + i, 1800, weights=(0.55, 0.15, 0.15, 0.15))
                for i in range(6)
            }
            for k in range(3)
        }
        comparison = key_averaged_proxy_comparison(by_key, ordinary)
        self.assertLess(comparison["base_entropy_bits"]["p_value"], 0.05)

    def test_symmetric_averaging_reports_both_spreads(self) -> None:
        wm = {
            f"draw_{k}": {f"case_{i}": random_dna(2000 + 10 * k + i, 1500) for i in range(5)}
            for k in range(3)
        }
        ord_ = {
            f"draw_{k}": {f"case_{i}": random_dna(3000 + 10 * k + i, 1500) for i in range(5)}
            for k in range(3)
        }
        comparison = symmetric_averaged_proxy_comparison(wm, ord_)
        self.assertEqual(set(comparison), set(PROXY_METRICS))
        for metric in PROXY_METRICS:
            row = comparison[metric]
            self.assertEqual(row["draws_per_arm"], 3.0)
            self.assertGreaterEqual(row["watermarked_spread_over_draws"], 0.0)
            self.assertGreaterEqual(row["ordinary_spread_over_draws"], 0.0)

    def test_symmetric_averaging_requires_equal_and_multiple_draws(self) -> None:
        one = {"draw_0": {f"case_{i}": random_dna(4000 + i, 900) for i in range(3)}}
        two = {
            f"draw_{k}": {f"case_{i}": random_dna(5000 + 10 * k + i, 900) for i in range(3)}
            for k in range(2)
        }
        with self.assertRaisesRegex(ValueError, "at least two draws"):
            symmetric_averaged_proxy_comparison(one, two)
        three = {
            f"draw_{k}": {f"case_{i}": random_dna(6000 + 10 * k + i, 900) for i in range(3)}
            for k in range(3)
        }
        with self.assertRaisesRegex(ValueError, "same number of draws"):
            symmetric_averaged_proxy_comparison(three, two)

    def test_comparison_validates_its_inputs(self) -> None:
        watermarked = {"a": random_dna(1, 600), "b": random_dna(2, 600)}
        with self.assertRaisesRegex(ValueError, "same prompts"):
            paired_proxy_comparison(watermarked, {"a": random_dna(3, 600)})
        with self.assertRaisesRegex(ValueError, "at least two prompts"):
            paired_proxy_comparison({"a": random_dna(1, 600)}, {"a": random_dna(2, 600)})
        with self.assertRaisesRegex(ValueError, "equal length"):
            paired_proxy_comparison(
                watermarked, {"a": random_dna(3, 600), "b": random_dna(4, 1200)}
            )


if __name__ == "__main__":
    unittest.main()
