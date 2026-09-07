from __future__ import annotations

import random
import unittest

from genomic_watermarks.gof import (
    g_statistic,
    monte_carlo_goodness_of_fit,
    observed_counts,
    summarize_p_values,
    token_goodness_of_fit,
)


class GoodnessOfFitTest(unittest.TestCase):
    def test_counts_follow_declared_item_order(self) -> None:
        self.assertEqual(observed_counts(("c", "a", "c"), ("a", "b", "c")), (1, 0, 2))

    def test_g_statistic_grows_with_deviation(self) -> None:
        self.assertEqual(g_statistic([50, 50], [0.5, 0.5]), 0.0)
        self.assertGreater(g_statistic([90, 10], [0.5, 0.5]), g_statistic([55, 45], [0.5, 0.5]))

    def test_draws_from_declared_law_are_not_rejected(self) -> None:
        probabilities = (0.4, 0.3, 0.2, 0.1)
        rng = random.Random(5)
        tokens = []
        for _ in range(2_000):
            value = rng.random()
            cumulative = 0.0
            for token, probability in zip("abcd", probabilities, strict=True):
                cumulative += probability
                if value < cumulative:
                    tokens.append(token)
                    break
        result = token_goodness_of_fit(
            tokens, tuple("abcd"), probabilities, replicates=500, seed=1
        )
        self.assertGreater(result.p_value, 0.05)
        self.assertEqual(result.draws, 2_000)

    def test_shifted_law_is_rejected(self) -> None:
        result = monte_carlo_goodness_of_fit(
            [1_000, 600, 300, 100], (0.4, 0.3, 0.2, 0.1), replicates=500, seed=1
        )
        self.assertLess(result.p_value, 0.01)

    def test_summary_applies_multiple_test_correction(self) -> None:
        summary = summarize_p_values({"a": 0.5, "b": 0.02, "c": 0.001, "d": 0.9})
        self.assertEqual(summary["tests"], 4.0)
        self.assertEqual(summary["rejections_at_bonferroni"], 1.0)


if __name__ == "__main__":
    unittest.main()
