from __future__ import annotations

import random
import unittest

from genomic_watermarks.dna import tokenize_fixed
from genomic_watermarks.synthid import KeyedTournament, score_synthid_tokens
from genomic_watermarks.synthid_boundary import (
    deterministic_single_base_edit,
    score_synthid_unknown_boundary,
)


class SynthIDUnknownBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tournament = KeyedTournament(
            key=b"public-boundary-unit-test-key",
            domain="boundary/unit-test",
            depth=7,
            context_tokens=4,
            context_history_size=1024,
        )

    def assert_matches_brute_force(self, dna: str, base_length: int) -> None:
        observed = score_synthid_unknown_boundary(
            dna,
            base_length=base_length,
            tournament=self.tournament,
        )
        self.assertEqual(len(observed), len(dna) - base_length + 1)
        self.assertEqual([row.base_start for row in observed], list(range(len(observed))))
        for row in observed:
            expected = score_synthid_tokens(
                tokenize_fixed(dna[row.base_start : row.base_start + base_length]),
                self.tournament,
            )
            self.assertEqual(row.g_ones, expected.g_ones)
            self.assertEqual(row.g_total, expected.g_total)
            self.assertEqual(row.scored_tokens, expected.scored_tokens)
            self.assertEqual(row.repeated_contexts, expected.repeated_contexts)
            self.assertAlmostEqual(row.statistic, expected.statistic, places=12)

    def test_cached_search_matches_every_literal_substring_without_repeats(self) -> None:
        rng = random.Random(2718)
        dna = "".join(rng.choice("ATCG") for _ in range(102))
        self.assert_matches_brute_force(dna, 48)

    def test_cached_search_matches_repetition_masking(self) -> None:
        dna = "A" * 102
        self.assert_matches_brute_force(dna, 48)
        scores = score_synthid_unknown_boundary(
            dna,
            base_length=48,
            tournament=self.tournament,
        )
        self.assertTrue(all(row.scored_tokens == 1 for row in scores))
        self.assertTrue(all(row.repeated_contexts == 3 for row in scores))

    def test_rejects_invalid_window_lengths(self) -> None:
        for length in (0, 31, 108):
            with self.assertRaises(ValueError):
                score_synthid_unknown_boundary(
                    "A" * 102,
                    base_length=length,
                    tournament=self.tournament,
                )


class DeterministicSingleBaseEditTest(unittest.TestCase):
    def test_each_condition_changes_exactly_one_base_event(self) -> None:
        dna = "ATCG" * 20
        substitution = deterministic_single_base_edit(
            dna, condition="substitution_1nt", case_id="case", draw_id=0
        )
        insertion = deterministic_single_base_edit(
            dna, condition="insertion_1nt", case_id="case", draw_id=0
        )
        deletion = deterministic_single_base_edit(
            dna, condition="deletion_1nt", case_id="case", draw_id=0
        )
        self.assertEqual(len(substitution.sequence), len(dna))
        self.assertEqual(
            sum(left != right for left, right in zip(dna, substitution.sequence, strict=True)),
            1,
        )
        self.assertNotEqual(substitution.original_base, substitution.edited_base)
        self.assertEqual(len(insertion.sequence), len(dna) + 1)
        self.assertEqual(len(deletion.sequence), len(dna) - 1)

    def test_identity_replays_and_changes_the_location(self) -> None:
        dna = "ATCG" * 100
        first = deterministic_single_base_edit(
            dna, condition="deletion_1nt", case_id="first", draw_id=1
        )
        replay = deterministic_single_base_edit(
            dna, condition="deletion_1nt", case_id="first", draw_id=1
        )
        other = deterministic_single_base_edit(
            dna, condition="deletion_1nt", case_id="other", draw_id=1
        )
        self.assertEqual(first, replay)
        self.assertNotEqual(first.position, other.position)

    def test_invalid_edit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            deterministic_single_base_edit(
                "AAAAAA", condition="substitution_1pct", case_id="case", draw_id=0
            )


if __name__ == "__main__":
    unittest.main()

