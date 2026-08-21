from __future__ import annotations

import random
import unittest
from collections import Counter

from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.sampling.partition import (
    keyed_balanced_partition,
    sample_categorical,
    sample_partition_coupling,
    select_group_maximal_coupling,
)


class PartitionTest(unittest.TestCase):
    def test_keyed_partition_is_balanced_deterministic_and_domain_separated(self) -> None:
        tokens = canonical_kmers()
        first = keyed_balanced_partition(tokens, b"fixture-key", domain="position/0")
        replay = keyed_balanced_partition(tokens, b"fixture-key", domain="position/0")
        other = keyed_balanced_partition(tokens, b"fixture-key", domain="position/1")
        self.assertEqual(first, replay)
        self.assertEqual(sum(first.values()), 2048)
        self.assertNotEqual(first, other)

    def test_balanced_mass_maps_latent_bit_exactly(self) -> None:
        rng = random.Random(7)
        self.assertFalse(select_group_maximal_coupling(False, 0.5, rng))
        self.assertTrue(select_group_maximal_coupling(True, 0.5, rng))

    def test_empirical_token_marginal_is_preserved(self) -> None:
        items = ("A", "B")
        probabilities = (0.8, 0.2)
        partition = {"A": True, "B": False}
        rng = random.Random(1729)
        counts: Counter[str] = Counter()
        agreements = 0
        draws = 100_000
        for _ in range(draws):
            latent = rng.random() < 0.5
            sample = sample_partition_coupling(items, probabilities, partition, latent, rng)
            counts[sample.token] += 1
            agreements += sample.agrees_with_latent
        self.assertAlmostEqual(counts["A"] / draws, 0.8, delta=0.006)
        self.assertAlmostEqual(counts["B"] / draws, 0.2, delta=0.006)
        self.assertAlmostEqual(agreements / draws, 0.7, delta=0.006)

    def test_zero_mass_group_is_never_selected(self) -> None:
        rng = random.Random(1)
        for latent in (False, True):
            sample = sample_partition_coupling(
                ("A", "B"),
                (1.0, 0.0),
                {"A": True, "B": False},
                latent,
                rng,
            )
            self.assertEqual(sample.token, "A")

    def test_categorical_sampling_normalizes_and_validates(self) -> None:
        self.assertEqual(sample_categorical(("A", "B"), (0.0, 5.0), random.Random(4)), "B")
        with self.assertRaises(ValueError):
            sample_categorical(("A",), (0.5, 0.5), random.Random(4))


if __name__ == "__main__":
    unittest.main()
