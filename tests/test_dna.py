from __future__ import annotations

import unittest

from genomic_watermarks.dna import (
    canonical_kmers,
    enumerate_hypotheses,
    normalize_dna,
    reverse_complement,
    tokenize_fixed,
)


class DnaTest(unittest.TestCase):
    def test_canonical_kmer_alphabet(self) -> None:
        kmers = canonical_kmers()
        self.assertEqual(len(kmers), 4096)
        self.assertEqual(len(set(kmers)), 4096)
        self.assertEqual(kmers[0], "AAAAAA")
        self.assertEqual(kmers[-1], "GGGGGG")

    def test_normalize_and_reverse_complement(self) -> None:
        self.assertEqual(normalize_dna(" atcg\nAT "), "ATCGAT")
        self.assertEqual(reverse_complement("ATCGAT"), "ATCGAT")
        with self.assertRaises(ValueError):
            normalize_dna("ATNCG")

    def test_fixed_tokenization_drops_partial_tail(self) -> None:
        sequence = "AAAAAATTTTTTCC"
        self.assertEqual(tokenize_fixed(sequence), ("AAAAAA", "TTTTTT"))
        self.assertEqual(tokenize_fixed(sequence, phase=1), ("AAAAAT", "TTTTTC"))
        with self.assertRaises(ValueError):
            tokenize_fixed(sequence, phase=6)

    def test_search_has_two_strands_and_six_phases(self) -> None:
        hypotheses = enumerate_hypotheses("ATCG" * 8)
        self.assertEqual(len(hypotheses), 12)
        self.assertEqual(
            {item.orientation for item in hypotheses}, {"forward", "reverse_complement"}
        )
        self.assertEqual({item.phase for item in hypotheses}, set(range(6)))


if __name__ == "__main__":
    unittest.main()
