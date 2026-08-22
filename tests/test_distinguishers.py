from __future__ import annotations

import random
import unittest

from genomic_watermarks.distinguishers import (
    DISTINGUISHERS,
    compression_features,
    exact_cluster_sign_flip_p_value,
    leave_one_prompt_out_forced_choice,
    matched_draw_forced_choice,
    proxy_features,
    trimer_features,
)
from genomic_watermarks.dna import BASES
from genomic_watermarks.sequence_proxies import PROXY_METRICS


def random_dna(seed: int, length: int, weights: tuple[float, ...] | None = None) -> str:
    rng = random.Random(seed)
    return "".join(rng.choices(tuple(BASES), weights=weights, k=length))


class FeatureTest(unittest.TestCase):
    def test_feature_widths_are_fixed(self) -> None:
        sequence = random_dna(1, 1200)
        self.assertEqual(len(proxy_features(sequence)), len(PROXY_METRICS))
        self.assertEqual(len(trimer_features(sequence)), 64)
        self.assertEqual(len(compression_features(sequence)), 1)

    def test_compression_is_lower_for_a_repetitive_sequence(self) -> None:
        repetitive = compression_features("ATCGGC" * 200)[0]
        random_like = compression_features(random_dna(2, 1200))[0]
        self.assertLess(repetitive, random_like)

    def test_every_declared_distinguisher_is_callable(self) -> None:
        sequence = random_dna(3, 600)
        for name, features in DISTINGUISHERS.items():
            self.assertGreater(len(features(sequence)), 0, name)


class ExactClusterTest(unittest.TestCase):
    def test_chance_performance_is_not_significant(self) -> None:
        # The pattern that made a naive prompt bootstrap exclude chance: every prompt at or
        # above one half, but the pooled count entirely unremarkable.
        counts = {f"case_{i}": c for i, c in enumerate([2, 2, 3, 3, 3, 2, 2, 2])}
        result = exact_cluster_sign_flip_p_value(counts, 4)
        self.assertEqual(result["correct"], 19.0)
        self.assertEqual(result["decisions"], 32.0)
        self.assertEqual(result["relabellings"], 256.0)
        self.assertGreater(result["p_value"], 0.2)

    def test_perfect_performance_hits_the_enumeration_floor(self) -> None:
        counts = {f"case_{i}": 4 for i in range(8)}
        result = exact_cluster_sign_flip_p_value(counts, 4)
        self.assertAlmostEqual(result["accuracy"], 1.0)
        self.assertAlmostEqual(result["p_value"], 2.0 / 256.0)

    def test_exactly_chance_gives_a_p_value_of_one(self) -> None:
        counts = {f"case_{i}": 2 for i in range(8)}
        self.assertAlmostEqual(exact_cluster_sign_flip_p_value(counts, 4)["p_value"], 1.0)

    def test_inputs_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "draws per prompt must be positive"):
            exact_cluster_sign_flip_p_value({"a": 1}, 0)
        with self.assertRaisesRegex(ValueError, "at least one prompt"):
            exact_cluster_sign_flip_p_value({}, 4)
        with self.assertRaisesRegex(ValueError, "limited to 20 prompts"):
            exact_cluster_sign_flip_p_value({f"c{i}": 1 for i in range(21)}, 4)
        with self.assertRaisesRegex(ValueError, r"lie in \[0, draws\]"):
            exact_cluster_sign_flip_p_value({"a": 9}, 4)


class ForcedChoiceTest(unittest.TestCase):
    def matched_arms(self, prompts: int = 6, keys: int = 2):
        ordinary = {f"case_{i}": random_dna(100 + i, 1800) for i in range(prompts)}
        watermarked = {
            f"key_{k}": {f"case_{i}": random_dna(500 + 50 * k + i, 1800) for i in range(prompts)}
            for k in range(keys)
        }
        return watermarked, ordinary

    def test_matched_arms_score_near_chance(self) -> None:
        watermarked, ordinary = self.matched_arms()
        for name in DISTINGUISHERS:
            result = leave_one_prompt_out_forced_choice(watermarked, ordinary, name)
            self.assertEqual(result.decisions, 12)
            self.assertLessEqual(result.accuracy, 0.85, name)
            self.assertGreaterEqual(result.accuracy, 0.15, name)

    def test_a_grossly_biased_arm_is_caught(self) -> None:
        """A distinguisher that cannot catch an obvious bias would prove nothing."""

        ordinary = {f"case_{i}": random_dna(200 + i, 1800) for i in range(6)}
        watermarked = {
            "key_0": {
                f"case_{i}": random_dna(300 + i, 1800, weights=(0.7, 0.1, 0.1, 0.1))
                for i in range(6)
            }
        }
        result = leave_one_prompt_out_forced_choice(watermarked, ordinary, "trimer_centroid")
        self.assertEqual(result.accuracy, 1.0)
        proxy = leave_one_prompt_out_forced_choice(watermarked, ordinary, "proxy_centroid")
        self.assertEqual(proxy.accuracy, 1.0)

    def test_per_prompt_accuracy_covers_every_prompt(self) -> None:
        watermarked, ordinary = self.matched_arms(prompts=5, keys=3)
        result = leave_one_prompt_out_forced_choice(watermarked, ordinary, "proxy_centroid")
        self.assertEqual(set(result.accuracy_by_prompt), set(ordinary))
        self.assertEqual(result.decisions, 15)
        self.assertAlmostEqual(
            sum(result.accuracy_by_prompt.values()) / 5, result.accuracy, places=9
        )

    def test_inputs_are_validated(self) -> None:
        watermarked, ordinary = self.matched_arms()
        with self.assertRaisesRegex(ValueError, "unknown distinguisher"):
            leave_one_prompt_out_forced_choice(watermarked, ordinary, "telepathy")
        with self.assertRaisesRegex(ValueError, "at least one key"):
            leave_one_prompt_out_forced_choice({}, ordinary, "proxy_centroid")
        with self.assertRaisesRegex(ValueError, "at least three prompts"):
            leave_one_prompt_out_forced_choice(
                {"key_0": {"a": random_dna(1, 600), "b": random_dna(2, 600)}},
                {"a": random_dna(3, 600), "b": random_dna(4, 600)},
                "proxy_centroid",
            )
        with self.assertRaisesRegex(ValueError, "same prompts as the control"):
            leave_one_prompt_out_forced_choice(
                {"key_0": {"case_0": random_dna(1, 600)}}, ordinary, "proxy_centroid"
            )

    def test_matched_draws_score_near_chance_on_matched_arms(self) -> None:
        pairs = {
            f"draw_{k}": {
                f"case_{i}": (
                    random_dna(7000 + 100 * k + i, 1800),
                    random_dna(8000 + 100 * k + i, 1800),
                )
                for i in range(6)
            }
            for k in range(3)
        }
        for name in DISTINGUISHERS:
            result = matched_draw_forced_choice(pairs, name)
            self.assertEqual(result.decisions, 18)
            self.assertLessEqual(result.accuracy, 0.85, name)
            self.assertGreaterEqual(result.accuracy, 0.15, name)

    def test_matched_draws_catch_a_gross_bias(self) -> None:
        pairs = {
            "draw_0": {
                f"case_{i}": (
                    random_dna(9000 + i, 1800, weights=(0.7, 0.1, 0.1, 0.1)),
                    random_dna(9500 + i, 1800),
                )
                for i in range(6)
            }
        }
        self.assertEqual(matched_draw_forced_choice(pairs, "trimer_centroid").accuracy, 1.0)

    def test_matched_draws_validate_inputs(self) -> None:
        pairs = {
            "draw_0": {
                f"case_{i}": (random_dna(100 + i, 900), random_dna(200 + i, 900)) for i in range(4)
            }
        }
        with self.assertRaisesRegex(ValueError, "unknown distinguisher"):
            matched_draw_forced_choice(pairs, "astrology")
        with self.assertRaisesRegex(ValueError, "at least one draw"):
            matched_draw_forced_choice({}, "proxy_centroid")
        with self.assertRaisesRegex(ValueError, "at least three prompts"):
            matched_draw_forced_choice(
                {"draw_0": {"a": (random_dna(1, 900), random_dna(2, 900))}}, "proxy_centroid"
            )
        with self.assertRaisesRegex(ValueError, "same prompts"):
            matched_draw_forced_choice(
                {**pairs, "draw_1": {"case_0": (random_dna(3, 900), random_dna(4, 900))}},
                "proxy_centroid",
            )

    def test_a_tie_counts_as_a_miss(self) -> None:
        """Identical arms give identical scores; ties must not be scored as wins."""

        shared = {f"case_{i}": random_dna(400 + i, 1800) for i in range(4)}
        result = leave_one_prompt_out_forced_choice({"key_0": shared}, shared, "proxy_centroid")
        self.assertEqual(result.accuracy, 0.0)


if __name__ == "__main__":
    unittest.main()
