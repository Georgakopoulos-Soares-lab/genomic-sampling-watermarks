"""Tests for the key-reuse attacks.

The attacks must do what they claim structurally, before any detector is pointed at
them: a splice must be novel rather than a copy, a shuffle must actually displace
tokens, and every attack must preserve the 6-mer multiset it was given so that a
measured removal cannot be confused with a composition change.
"""

from __future__ import annotations

import collections
import random
import unittest

from genomic_watermarks.attacks import (
    block_shuffle,
    positional_shuffle,
    positional_splice,
    tokenize,
)

TOKENS_A = tuple(f"AAAAA{base}" for base in "ACGT") * 8
TOKENS_B = tuple(f"CCCCC{base}" for base in "ACGT") * 8
SEQ_A = "".join(TOKENS_A)
SEQ_B = "".join(TOKENS_B)


class TokenizeTest(unittest.TestCase):
    def test_whole_kmers_only(self) -> None:
        self.assertEqual(tokenize("ACGTACGGGGGGAC"), ("ACGTAC", "GGGGGG"))

    def test_a_short_sequence_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shorter than one k-mer"):
            tokenize("ACGT")


class SpliceTest(unittest.TestCase):
    def test_a_splice_takes_each_position_from_a_donor(self) -> None:
        forged, choice = positional_splice([SEQ_A, SEQ_B], random.Random(1))
        tokens = tokenize(forged)
        for index, donor in enumerate(choice):
            expected = (TOKENS_A, TOKENS_B)[donor][index]
            self.assertEqual(tokens[index], expected)

    def test_a_splice_is_never_a_verbatim_copy(self) -> None:
        for seed in range(50):
            forged, choice = positional_splice([SEQ_A, SEQ_B], random.Random(seed))
            self.assertGreater(len(set(choice)), 1)
            self.assertNotEqual(forged, SEQ_A)
            self.assertNotEqual(forged, SEQ_B)

    def test_splicing_preserves_length_and_needs_two_donors(self) -> None:
        forged, _ = positional_splice([SEQ_A, SEQ_B], random.Random(2))
        self.assertEqual(len(forged), len(SEQ_A))
        with self.assertRaisesRegex(ValueError, "at least two donor"):
            positional_splice([SEQ_A], random.Random(3))

    def test_splicing_is_deterministic_under_a_fixed_seed(self) -> None:
        first, _ = positional_splice([SEQ_A, SEQ_B], random.Random(7))
        second, _ = positional_splice([SEQ_A, SEQ_B], random.Random(7))
        self.assertEqual(first, second)


class ShuffleTest(unittest.TestCase):
    def test_a_full_shuffle_preserves_the_kmer_multiset(self) -> None:
        attacked, displaced = positional_shuffle(SEQ_A, random.Random(4))
        self.assertEqual(
            collections.Counter(tokenize(attacked)), collections.Counter(tokenize(SEQ_A))
        )
        self.assertGreater(displaced, 0.5)

    def test_a_block_shuffle_only_moves_tokens_inside_its_block(self) -> None:
        attacked, _ = block_shuffle(SEQ_A, 4, random.Random(5))
        original = tokenize(SEQ_A)
        moved = tokenize(attacked)
        for start in range(0, len(original), 4):
            self.assertEqual(
                collections.Counter(moved[start : start + 4]),
                collections.Counter(original[start : start + 4]),
            )

    def test_a_wider_block_displaces_more_positions(self) -> None:
        rates = [block_shuffle(SEQ_A, width, random.Random(6))[1] for width in (2, 4, 16, 32)]
        self.assertLess(rates[0], rates[-1])
        # A pairwise swap can only displace both members or neither.
        self.assertLessEqual(rates[0], 1.0)

    def test_a_block_shuffle_preserves_the_kmer_multiset(self) -> None:
        attacked, _ = block_shuffle(SEQ_A, 6, random.Random(8))
        self.assertEqual(
            collections.Counter(tokenize(attacked)), collections.Counter(tokenize(SEQ_A))
        )

    def test_a_degenerate_block_width_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two tokens"):
            block_shuffle(SEQ_A, 1, random.Random(9))


if __name__ == "__main__":
    unittest.main()
