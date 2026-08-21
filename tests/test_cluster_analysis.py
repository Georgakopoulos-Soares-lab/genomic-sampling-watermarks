from __future__ import annotations

import unittest

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters


class PromptClusterAnalysisTest(unittest.TestCase):
    def test_bootstrap_is_deterministic_and_prompt_weighted(self) -> None:
        values = {
            "one": (0.10, 0.20),
            "two": (0.20, 0.30),
            "three": (0.30, 0.40),
        }
        first = analyze_prompt_clusters(values, bootstrap_replicates=2_000, bootstrap_seed=7)
        replay = analyze_prompt_clusters(values, bootstrap_replicates=2_000, bootstrap_seed=7)
        self.assertEqual(first, replay)
        self.assertAlmostEqual(first.overall_mean, 0.25)
        self.assertLessEqual(first.interval_lower, first.overall_mean)
        self.assertGreaterEqual(first.interval_upper, first.overall_mean)
        self.assertAlmostEqual(first.maximum_leave_one_out_change, 0.05)

    def test_each_prompt_has_equal_weight_despite_different_row_counts(self) -> None:
        result = analyze_prompt_clusters(
            {"short": (0.0,), "long": (1.0,) * 99},
            bootstrap_replicates=100,
            bootstrap_seed=1,
        )
        self.assertEqual(result.overall_mean, 0.5)

    def test_invalid_cluster_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyze_prompt_clusters(
                {"only": (0.1,)},
                bootstrap_replicates=100,
                bootstrap_seed=1,
            )
        with self.assertRaises(ValueError):
            analyze_prompt_clusters(
                {"one": (), "two": (0.2,)},
                bootstrap_replicates=100,
                bootstrap_seed=1,
            )
