"""Tests for the order-sensitive proxies.

The point of these two measures is that they see what a composition statistic
cannot: a rearrangement of whole 6-mers. So the decisive tests here are the ones
that shuffle a sequence and check that these metrics move while the 6-mer multiset
does not.
"""

from __future__ import annotations

import collections
import random
import unittest

from genomic_watermarks.attacks import block_shuffle, positional_shuffle, tokenize
from genomic_watermarks.sequence_proxies import proxy_metrics
from genomic_watermarks.structure_proxies import (
    MINIMUM_ORF_CODONS,
    STRUCTURE_METRICS,
    MarkovReference,
    fit_reference,
    open_reading_frames,
    orf_summary,
    relative_shift,
    structure_metrics,
)

# A start codon, 30 harmless in-frame codons, then a stop. 96 bases, one clean ORF.
CODING = "ATG" + "GCTACGATCAAGCTTGCAACCGTTGGCAAT" * 3 + "TAA"


def coding_sequence(copies: int = 6) -> str:
    return CODING * copies


def stop_rich_background(rng: random.Random, codons: int) -> str:
    """Background DNA where chance reading frames stay short.

    Uniform random DNA contains long open reading frames by chance --- a 1.8 kb
    random sequence routinely carries one over 200 bases --- so a uniform background
    would swamp an embedded frame and make this test measure nothing. Sprinkling stop
    codons keeps chance frames well under the 25-codon minimum, so the only long
    frame in the fixture is the one deliberately placed there.
    """

    pieces = []
    for _ in range(codons):
        if rng.random() < 0.2:
            pieces.append(rng.choice(("TAA", "TAG", "TGA")))
        else:
            pieces.append("".join(rng.choice("ACGT") for _ in range(3)))
    return "".join(pieces)


def realistic_sequence(seed: int = 21, background_codons: int = 500) -> str:
    """Stop-rich background with one dominant reading frame embedded in it."""

    rng = random.Random(seed)
    left = stop_rich_background(rng, background_codons // 2)
    right = stop_rich_background(rng, background_codons // 2)
    return left + CODING * 3 + right


def reference_model() -> MarkovReference:
    rng = random.Random(11)
    bases = "ACGT"
    corpus = ["".join(rng.choice(bases) for _ in range(4000)) for _ in range(4)]
    corpus.append(coding_sequence(4))
    return fit_reference(corpus, order=3)


class OpenReadingFrameTest(unittest.TestCase):
    def test_a_clean_reading_frame_is_found(self) -> None:
        orfs = open_reading_frames(CODING, minimum_codons=5, both_strands=False)
        self.assertTrue(orfs)
        start, length = orfs[0]
        self.assertEqual(start, 0)
        self.assertEqual(length, len(CODING))

    def test_a_frame_shorter_than_the_minimum_is_ignored(self) -> None:
        short = "ATG" + "GCT" * 3 + "TAA"
        self.assertEqual(open_reading_frames(short, minimum_codons=25), ())
        self.assertTrue(open_reading_frames(short, minimum_codons=3, both_strands=False))

    def test_reverse_strand_frames_are_searched(self) -> None:
        # Reverse complement of the coding sequence: the ORF exists only on the other
        # strand, so it is found with both_strands and not without.
        from genomic_watermarks.dna import reverse_complement

        flipped = reverse_complement(CODING)
        self.assertTrue(open_reading_frames(flipped, minimum_codons=5, both_strands=True))
        forward_only = open_reading_frames(flipped, minimum_codons=5, both_strands=False)
        self.assertEqual(forward_only, ())

    def test_a_degenerate_minimum_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "start and a stop"):
            open_reading_frames(CODING, minimum_codons=1)

    def test_the_summary_reports_coverage_without_double_counting(self) -> None:
        summary = orf_summary(coding_sequence(2), minimum_codons=5)
        self.assertGreater(summary["longest_orf_bases"], 0.0)
        self.assertGreaterEqual(summary["orf_count"], 2.0)
        self.assertLessEqual(summary["orf_coding_fraction"], 1.0)


class IndependentModelTest(unittest.TestCase):
    def test_reference_sequence_scores_better_than_a_foreign_one(self) -> None:
        rng = random.Random(3)
        corpus = ["".join(rng.choice("ACGT") for _ in range(3000)) for _ in range(3)]
        skewed = "".join(rng.choices("AT", weights=[3, 1], k=3000))
        model = fit_reference(corpus + [skewed] * 6, order=3)
        self.assertGreater(
            model.mean_log2_probability(skewed), model.mean_log2_probability(corpus[0])
        )

    def test_an_unfitted_model_refuses_to_score(self) -> None:
        with self.assertRaisesRegex(ValueError, "not been fitted"):
            MarkovReference(order=2).mean_log2_probability(CODING)

    def test_inputs_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, r"order must lie in \[1, 6\]"):
            MarkovReference(order=0)
        with self.assertRaisesRegex(ValueError, "no reference sequence was long enough"):
            fit_reference(["AC"], order=3)
        model = reference_model()
        with self.assertRaisesRegex(ValueError, "shorter than the model order"):
            model.mean_log2_probability("AC")

    def test_scores_are_negative_log_probabilities_per_base(self) -> None:
        model = reference_model()
        score = model.mean_log2_probability(coding_sequence(2))
        # Four bases, so a uniform model would score -2 bits per base.
        self.assertLess(score, 0.0)
        self.assertGreater(score, -4.0)


class BlindnessTest(unittest.TestCase):
    """The reason these metrics exist."""

    def setUp(self) -> None:
        self.model = reference_model()
        self.sequence = realistic_sequence()

    def test_a_shuffle_preserves_the_kmer_multiset(self) -> None:
        attacked, _ = positional_shuffle(self.sequence, random.Random(5))
        self.assertEqual(
            collections.Counter(tokenize(attacked)),
            collections.Counter(tokenize(self.sequence)),
        )

    def test_order_invariant_proxies_do_not_move_at_all_but_the_orf_measure_does(self) -> None:
        """The blindness this module exists to fix, asserted without magic numbers.

        A 6-mer permutation preserves the 6-mer multiset exactly, so any proxy that
        is a function of base or k-mer counts alone cannot move by even a rounding
        error. Those are asserted to be identical rather than merely close. The
        longest open reading frame is not such a function --- a frame spans 6-mer
        junctions --- so it does move.

        Magnitudes are deliberately not asserted here. How much the ORF measure moves
        depends on how much frame structure the sequence had, which is a property of
        real generated DNA and belongs in a measured experiment, not in a fixture.
        """

        attacked, _ = positional_shuffle(self.sequence, random.Random(5))
        self.assertEqual(
            collections.Counter(tokenize(attacked)),
            collections.Counter(tokenize(self.sequence)),
        )
        before = proxy_metrics(self.sequence)
        after = proxy_metrics(attacked)
        # Exactly count-determined, so exactly unchanged.
        for metric in ("gc_fraction", "base_entropy_bits", "purine_fraction"):
            self.assertEqual(after[metric], before[metric], metric)

        structure_before = structure_metrics(self.sequence, self.model)
        structure_after = structure_metrics(attacked, self.model)
        self.assertNotEqual(
            structure_after["longest_orf_bases"], structure_before["longest_orf_bases"]
        )
        self.assertLess(structure_after["longest_orf_bases"], structure_before["longest_orf_bases"])

    def test_the_independent_model_score_is_nearly_blind_too(self) -> None:
        """A measured negative, recorded so nobody assumes otherwise.

        A Markov model fitted on reference DNA scores high-entropy sequence at close
        to the uniform rate, and a 6-mer permutation barely changes that: the model
        conditions on a few preceding bases and a shuffle leaves most of those
        contexts intact. So this instrument does not price a rearrangement, and among
        the two declared structure measures only the reading-frame one does.
        """

        attacked, _ = positional_shuffle(self.sequence, random.Random(5))
        shifts = relative_shift(
            structure_metrics(attacked, self.model),
            structure_metrics(self.sequence, self.model),
        )
        self.assertLess(shifts["independent_model_mean_log2_probability"], 0.05)
        self.assertGreater(
            shifts["longest_orf_bases"], shifts["independent_model_mean_log2_probability"]
        )

    def test_a_wider_block_destroys_more_structure(self) -> None:
        narrow, _ = block_shuffle(self.sequence, 2, random.Random(7))
        wide, _ = block_shuffle(self.sequence, 32, random.Random(7))
        reference = structure_metrics(self.sequence, self.model)
        narrow_shift = relative_shift(structure_metrics(narrow, self.model), reference)[
            "longest_orf_bases"
        ]
        wide_shift = relative_shift(structure_metrics(wide, self.model), reference)[
            "longest_orf_bases"
        ]
        self.assertGreaterEqual(wide_shift, narrow_shift)

    def test_every_declared_metric_is_produced(self) -> None:
        metrics = structure_metrics(self.sequence, self.model)
        self.assertEqual(set(metrics), set(STRUCTURE_METRICS))
        self.assertEqual(MINIMUM_ORF_CODONS, 25)


if __name__ == "__main__":
    unittest.main()
