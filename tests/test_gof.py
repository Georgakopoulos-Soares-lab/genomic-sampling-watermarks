from __future__ import annotations

import random
import unittest

from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.gof import (
    g_statistic,
    monte_carlo_goodness_of_fit,
    observed_counts,
    summarize_p_values,
    token_goodness_of_fit,
)
from genomic_watermarks.sampling.partition import select_group_maximal_coupling
from genomic_watermarks.watermark import (
    KeyedPartitionStream,
    generate_partition_mc,
)

PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v1"


class GStatisticTest(unittest.TestCase):
    def test_perfect_fit_gives_zero(self) -> None:
        self.assertAlmostEqual(g_statistic([50, 50], [0.5, 0.5]), 0.0)

    def test_statistic_grows_with_deviation(self) -> None:
        near = g_statistic([55, 45], [0.5, 0.5])
        far = g_statistic([90, 10], [0.5, 0.5])
        self.assertGreater(far, near)
        self.assertGreater(near, 0.0)

    def test_statistic_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "same length"):
            g_statistic([1, 2, 3], [0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "at least one observation"):
            g_statistic([0, 0], [0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "non-negative"):
            g_statistic([-1, 5], [0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "zero declared probability"):
            g_statistic([1, 5], [0.0, 1.0])


class ObservedCountsTest(unittest.TestCase):
    def test_counts_follow_declared_item_order(self) -> None:
        items = ("a", "b", "c")
        self.assertEqual(observed_counts(("c", "a", "c"), items), (1, 0, 2))

    def test_counts_reject_unknown_or_duplicate_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the declared support"):
            observed_counts(("z",), ("a", "b"))
        with self.assertRaisesRegex(ValueError, "must be unique"):
            observed_counts(("a",), ("a", "a"))
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            observed_counts(("a",), ())


class MonteCarloGoodnessOfFitTest(unittest.TestCase):
    def test_draws_from_the_declared_law_are_not_rejected(self) -> None:
        probabilities = (0.4, 0.3, 0.2, 0.1)
        rng = random.Random(5)
        counts = [0] * 4
        for _ in range(2000):
            value = rng.random()
            cumulative = 0.0
            for index, probability in enumerate(probabilities):
                cumulative += probability
                if value < cumulative:
                    counts[index] += 1
                    break
        result = monte_carlo_goodness_of_fit(counts, probabilities, replicates=500, seed=1)
        self.assertGreater(result.p_value, 0.05)
        self.assertEqual(result.draws, 2000)
        self.assertEqual(result.categories, 4)
        self.assertEqual(result.support_categories, 4)

    def test_a_shifted_law_is_rejected(self) -> None:
        result = monte_carlo_goodness_of_fit(
            [1000, 600, 300, 100],
            (0.4, 0.3, 0.2, 0.1),
            replicates=500,
            seed=1,
        )
        self.assertLess(result.p_value, 0.01)

    def test_p_value_is_never_zero_and_validates_arguments(self) -> None:
        result = monte_carlo_goodness_of_fit([500, 0], (0.5, 0.5), replicates=99, seed=0)
        self.assertGreaterEqual(result.p_value, 1 / 100)
        with self.assertRaisesRegex(ValueError, "replicates must be positive"):
            monte_carlo_goodness_of_fit([1, 1], (0.5, 0.5), replicates=0, seed=0)
        with self.assertRaisesRegex(ValueError, "seed must be non-negative"):
            monte_carlo_goodness_of_fit([1, 1], (0.5, 0.5), replicates=10, seed=-1)

    def test_result_is_deterministic_for_a_fixed_seed(self) -> None:
        first = monte_carlo_goodness_of_fit([60, 40], (0.5, 0.5), replicates=200, seed=3)
        second = monte_carlo_goodness_of_fit([60, 40], (0.5, 0.5), replicates=200, seed=3)
        self.assertEqual(first, second)


class WatermarkPreservationTest(unittest.TestCase):
    def test_partition_mc_draws_pass_the_fixed_state_test(self) -> None:
        items = canonical_kmers()[:32]
        weights = tuple(1.0 / (index + 1) for index in range(32))
        total = sum(weights)
        probabilities = tuple(weight / total for weight in weights)

        def draw(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            return items, probabilities

        rng = random.Random(2718)
        tokens: list[str] = []
        for trial in range(40):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"gof/{trial}")
            result = generate_partition_mc(draw, "ATCGGC", steps=100, stream=stream, rng=rng)
            tokens.extend(result.tokens)
        outcome = token_goodness_of_fit(tokens, items, probabilities, replicates=400, seed=11)
        self.assertEqual(outcome.draws, 4000)
        self.assertGreater(outcome.p_value, 0.01)

    def test_a_broken_within_group_draw_is_rejected(self) -> None:
        """A plausible bug — uniform inside the coupled group — must be caught."""

        items = canonical_kmers()[:32]
        weights = tuple(1.0 / (index + 1) for index in range(32))
        total = sum(weights)
        probabilities = tuple(weight / total for weight in weights)
        rng = random.Random(31)
        tokens: list[str] = []
        for trial in range(40):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"broken/{trial}")
            for index in range(100):
                partition = stream.partition(items, index)
                latent = stream.latent_bit(index)
                mass = sum(
                    probability
                    for item, probability in zip(items, probabilities, strict=True)
                    if partition[item]
                )
                group = select_group_maximal_coupling(latent, mass, rng)
                group_items = [item for item in items if partition[item] == group]
                tokens.append(rng.choice(group_items))
        outcome = token_goodness_of_fit(tokens, items, probabilities, replicates=400, seed=13)
        self.assertLess(outcome.p_value, 0.01)

    def test_token_goodness_of_fit_requires_tokens(self) -> None:
        with self.assertRaisesRegex(ValueError, "tokens must not be empty"):
            token_goodness_of_fit((), ("a", "b"), (0.5, 0.5), replicates=10, seed=0)


class SummarizePValuesTest(unittest.TestCase):
    def test_summary_reports_family_size_and_bonferroni_scope(self) -> None:
        summary = summarize_p_values({"a": 0.5, "b": 0.02, "c": 0.001, "d": 0.9})
        self.assertEqual(summary["tests"], 4.0)
        self.assertEqual(summary["rejections_at_alpha"], 2.0)
        self.assertAlmostEqual(summary["rejection_fraction"], 0.5)
        self.assertAlmostEqual(summary["expected_rejections_under_null"], 0.2)
        self.assertAlmostEqual(summary["bonferroni_alpha"], 0.0125)
        self.assertEqual(summary["rejections_at_bonferroni"], 1.0)
        self.assertAlmostEqual(summary["minimum_p_value"], 0.001)

    def test_summary_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one p-value"):
            summarize_p_values({})
        with self.assertRaisesRegex(ValueError, "alpha must lie"):
            summarize_p_values({"a": 0.5}, alpha=0.0)
        with self.assertRaisesRegex(ValueError, r"must lie in \[0, 1\]"):
            summarize_p_values({"a": 1.5})


if __name__ == "__main__":
    unittest.main()
