from __future__ import annotations

import inspect
import itertools
import math
import random
import unittest

from genomic_watermarks.dna import reverse_complement, tokenize_fixed
from genomic_watermarks.synthid import (
    KeyedTournament,
    generate_synthid,
    score_synthid_tokens,
)
from genomic_watermarks.synthid_boundary import deterministic_single_base_edit
from genomic_watermarks.synthid_position_independent import (
    FORWARD,
    REVERSE_COMPLEMENT,
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
    fair_binomial_log_survival_probability,
    fair_binomial_survival_probability,
)

PUBLIC_KEY = b"public-position-independent-unit-test-key"
DOMAIN = "position-independent/unit-test"


def deterministic_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ATCG") for _ in range(length))


def watermarked_dna() -> str:
    candidates = tuple(
        "".join(chars) for chars in itertools.islice(itertools.product("ATCG", repeat=6), 64)
    )

    def uniform_distribution(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return candidates, tuple(1.0 for _ in candidates)

    tournament = KeyedTournament(key=PUBLIC_KEY, domain=DOMAIN)
    return generate_synthid(
        uniform_distribution,
        "",
        steps=64,
        tournament=tournament,
        rng=random.Random(20260902),
    ).dna


class ExactBinomialTailTest(unittest.TestCase):
    def test_matches_literal_fair_coin_enumeration(self) -> None:
        for total in range(1, 21):
            for successes in range(total + 1):
                expected = sum(
                    math.comb(total, count) for count in range(successes, total + 1)
                ) / (2**total)
                self.assertAlmostEqual(
                    fair_binomial_survival_probability(successes, total),
                    expected,
                    delta=1e-13,
                )

    def test_rejects_impossible_counts(self) -> None:
        for successes, total in ((-1, 10), (11, 10), (0, 0)):
            with self.assertRaises(ValueError):
                fair_binomial_survival_probability(successes, total)

    def test_log_tail_retains_values_below_float_underflow(self) -> None:
        log_tail = fair_binomial_log_survival_probability(2_000, 2_000)
        self.assertAlmostEqual(log_tail, -2_000 * math.log(2.0))
        self.assertTrue(math.isfinite(log_tail))
        self.assertEqual(fair_binomial_survival_probability(2_000, 2_000), 0.0)


class PositionIndependentSynthIDDetectorTest(unittest.TestCase):
    def test_interface_accepts_no_prompt_boundary_phase_or_offset(self) -> None:
        parameters = inspect.signature(detect_synthid_position_independent).parameters
        self.assertEqual(tuple(parameters), ("sequence", "key", "domain", "config"))

    def test_search_count_covers_every_start_length_and_orientation(self) -> None:
        sequence = deterministic_dna(102, seed=1)
        config = PositionIndependentSynthIDConfig(
            window_base_lengths=(48, 60),
            depth=7,
        )
        result = detect_synthid_position_independent(
            sequence,
            key=PUBLIC_KEY,
            domain=DOMAIN,
            config=config,
        )
        expected = 2 * ((len(sequence) - 48 + 1) + (len(sequence) - 60 + 1))
        self.assertEqual(result.hypotheses_searched, expected)
        self.assertEqual(result.orientations_searched, (FORWARD, REVERSE_COMPLEMENT))
        self.assertEqual(result.window_base_lengths_searched, (48, 60))
        self.assertAlmostEqual(
            result.sequence_p_value,
            min(1.0, expected * result.minimum_local_p_value),
        )
        self.assertAlmostEqual(
            result.sequence_log_p_value,
            min(0.0, math.log(expected) + result.minimum_local_log_p_value),
        )

    def test_finds_one_watermark_after_two_different_unknown_prefix_lengths(self) -> None:
        marked = watermarked_dna()
        tournament = KeyedTournament(key=PUBLIC_KEY, domain=DOMAIN)
        aligned = score_synthid_tokens(tokenize_fixed(marked), tournament)
        aligned_log_p = fair_binomial_log_survival_probability(
            aligned.g_ones,
            aligned.g_total,
        )
        config = PositionIndependentSynthIDConfig(window_base_lengths=(len(marked),))

        reads = (
            deterministic_dna(7, seed=2) + marked + deterministic_dna(109, seed=3),
            deterministic_dna(71, seed=4) + marked + deterministic_dna(45, seed=5),
        )
        for read in reads:
            result = detect_synthid_position_independent(
                read,
                key=PUBLIC_KEY,
                domain=DOMAIN,
                config=config,
            )
            self.assertTrue(result.detected)
            self.assertLessEqual(result.minimum_local_log_p_value, aligned_log_p + 1e-12)

    def test_reverse_complement_has_the_same_complete_search_result(self) -> None:
        marked = watermarked_dna()
        read = deterministic_dna(37, seed=6) + marked + deterministic_dna(43, seed=7)
        config = PositionIndependentSynthIDConfig(window_base_lengths=(len(marked),))
        forward = detect_synthid_position_independent(
            read,
            key=PUBLIC_KEY,
            domain=DOMAIN,
            config=config,
        )
        reversed_read = detect_synthid_position_independent(
            reverse_complement(read),
            key=PUBLIC_KEY,
            domain=DOMAIN,
            config=config,
        )
        self.assertTrue(forward.detected)
        self.assertTrue(reversed_read.detected)
        self.assertEqual(forward.hypotheses_searched, reversed_read.hypotheses_searched)
        self.assertEqual(forward.minimum_local_p_value, reversed_read.minimum_local_p_value)
        self.assertEqual(forward.sequence_p_value, reversed_read.sequence_p_value)

    def test_finds_watermark_after_each_single_base_edit(self) -> None:
        marked = watermarked_dna()
        prefix = deterministic_dna(53, seed=9)
        suffix = deterministic_dna(67, seed=10)
        config = PositionIndependentSynthIDConfig(window_base_lengths=(len(marked),))
        for condition in ("substitution_1nt", "insertion_1nt", "deletion_1nt"):
            edited = deterministic_single_base_edit(
                marked,
                condition=condition,
                case_id="position-independent",
                draw_id=0,
            ).sequence
            result = detect_synthid_position_independent(
                prefix + edited + suffix,
                key=PUBLIC_KEY,
                domain=DOMAIN,
                config=config,
            )
            self.assertTrue(result.detected, condition)

    def test_reports_best_reverse_complement_interval_in_original_coordinates(self) -> None:
        marked = watermarked_dna()
        read = reverse_complement(marked)
        config = PositionIndependentSynthIDConfig(
            window_base_lengths=(len(marked),),
            orientations=(REVERSE_COMPLEMENT,),
        )
        result = detect_synthid_position_independent(
            read,
            key=PUBLIC_KEY,
            domain=DOMAIN,
            config=config,
        )
        self.assertTrue(result.detected)
        self.assertEqual(result.best_hypothesis.orientation, REVERSE_COMPLEMENT)
        self.assertEqual(result.best_hypothesis.oriented_start, 0)
        self.assertEqual(result.best_hypothesis.original_start, 0)
        self.assertEqual(result.best_hypothesis.original_stop, len(marked))

    def test_skips_only_lengths_that_do_not_fit_the_read(self) -> None:
        sequence = deterministic_dna(90, seed=8)
        config = PositionIndependentSynthIDConfig(
            window_base_lengths=(48, 96),
            orientations=(FORWARD,),
            depth=7,
        )
        result = detect_synthid_position_independent(
            sequence,
            key=PUBLIC_KEY,
            domain=DOMAIN,
            config=config,
        )
        self.assertEqual(result.window_base_lengths_searched, (48,))
        self.assertEqual(result.hypotheses_searched, len(sequence) - 48 + 1)

    def test_rejects_invalid_detector_configuration(self) -> None:
        invalid_options = (
            {"window_base_lengths": ()},
            {"window_base_lengths": (48, 48)},
            {"window_base_lengths": (47,)},
            {"orientations": ("backward",)},
            {"target_false_positive_rate": 1.0},
        )
        for options in invalid_options:
            with self.assertRaises(ValueError):
                PositionIndependentSynthIDConfig(**options)


if __name__ == "__main__":
    unittest.main()
