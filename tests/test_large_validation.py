from __future__ import annotations

import unittest

from genomic_watermarks.large_validation import (
    benjamini_hochberg,
    cluster_sign_flip_test,
    deterministic_prompt_split,
    exact_mcnemar_p_value,
    fixture_key,
    paired_cluster_summary,
    poisson_binomial_two_sided_p_value,
    sequence_identity,
)


class LargeValidationTest(unittest.TestCase):
    def test_fixture_keys_preserve_index_zero_and_separate_draws(self) -> None:
        self.assertEqual(
            fixture_key(0),
            b"genomic-sampling-watermarks/public-generation-fixture/v1",
        )
        self.assertEqual(fixture_key(2), fixture_key(2))
        self.assertNotEqual(fixture_key(1), fixture_key(2))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            fixture_key(-1)

    def test_sequence_identity_includes_draw(self) -> None:
        first = sequence_identity({"case_id": "p", "draw_id": 0, "scheme": "ordinary"})
        second = sequence_identity({"case_id": "p", "draw_id": 1, "scheme": "ordinary"})
        self.assertNotEqual(first, second)

    def test_hash_split_is_exact_deterministic_and_disjoint(self) -> None:
        case_ids = [f"case_{index:03d}" for index in range(256)]
        first = deterministic_prompt_split(case_ids, calibration_prompts=64)
        replay = deterministic_prompt_split(tuple(reversed(case_ids)), calibration_prompts=64)
        self.assertEqual(first, replay)
        self.assertEqual(sum(value == "calibration" for value in first.values()), 64)
        self.assertEqual(sum(value == "evaluation" for value in first.values()), 192)

    def test_bh_adjustment_is_monotone_in_rank(self) -> None:
        adjusted = benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.5})
        self.assertAlmostEqual(adjusted["a"], 0.003)
        self.assertAlmostEqual(adjusted["b"], 0.03)
        self.assertAlmostEqual(adjusted["c"], 0.5)

    def test_cluster_sign_flip_uses_prompt_as_unit(self) -> None:
        values = {
            "p1": (1.0, 1.2, 0.8, 1.1),
            "p2": (0.9, 1.0, 1.1, 1.2),
            "p3": (1.3, 1.1, 0.9, 1.0),
            "p4": (1.0, 1.0, 1.0, 1.0),
        }
        first = cluster_sign_flip_test(values, replicates=2_000, seed=7)
        replay = cluster_sign_flip_test(values, replicates=2_000, seed=7)
        self.assertEqual(first, replay)
        self.assertLess(first, 0.2)
        summary = paired_cluster_summary(
            values,
            bootstrap_replicates=1_000,
            permutation_replicates=2_000,
            seed=7,
        )
        self.assertEqual(summary.prompts, 4)
        self.assertEqual(summary.pairs, 16)
        self.assertGreater(summary.interval_lower, 0.0)

    def test_exact_mcnemar_counts_discordant_pairs(self) -> None:
        result = exact_mcnemar_p_value(
            [True, True, True, False],
            [False, False, True, False],
        )
        self.assertEqual(result["watermarked_only"], 2)
        self.assertEqual(result["ordinary_only"], 0)
        self.assertEqual(result["p_value"], 0.5)

    def test_poisson_binomial_fit_handles_rare_events_exactly(self) -> None:
        p_value = poisson_binomial_two_sided_p_value([0.009804444940051912] * 512, 2)
        self.assertAlmostEqual(p_value, 0.24350634853934522)
        self.assertGreater(p_value, 0.05)

    def test_poisson_binomial_fit_rejects_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            poisson_binomial_two_sided_p_value([], 0)
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            poisson_binomial_two_sided_p_value([1.1], 0)
        with self.assertRaisesRegex(ValueError, "observed successes"):
            poisson_binomial_two_sided_p_value([0.5], 2)


if __name__ == "__main__":
    unittest.main()
