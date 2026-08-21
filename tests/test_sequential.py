from __future__ import annotations

import unittest

from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.sequential import (
    build_evaluation_partitions,
    derive_path_seed,
    evaluation_partition_domains,
    path_rng,
    public_evaluation_material,
    public_evaluation_material_sha256,
)


class SequentialPilotTest(unittest.TestCase):
    def test_partition_domains_are_paired_and_deterministic(self) -> None:
        first = evaluation_partition_domains("cohort", "G_bp", 3)
        self.assertEqual(first, evaluation_partition_domains("cohort", "G_bp", 3))
        self.assertEqual(len(first), 3)
        self.assertEqual(len(set(first)), 3)
        self.assertNotEqual(first, evaluation_partition_domains("cohort", "G_tok", 3))

    def test_public_material_identifier_matches_bytes(self) -> None:
        import hashlib

        observed = hashlib.sha256(public_evaluation_material()).hexdigest()
        self.assertEqual(observed, public_evaluation_material_sha256())

    def test_partitions_are_balanced(self) -> None:
        partitions = build_evaluation_partitions(
            canonical_kmers(),
            cohort_id="cohort",
            policy_id="G_bp",
            count=2,
        )
        self.assertEqual(len(partitions), 2)
        self.assertTrue(all(sum(partition.values()) == 2048 for partition in partitions))
        self.assertNotEqual(partitions[0], partitions[1])

    def test_path_seed_is_stable_and_domain_separated(self) -> None:
        seed = derive_path_seed(1729, "G_bp", "prompt-1")
        self.assertEqual(seed, derive_path_seed(1729, "G_bp", "prompt-1"))
        self.assertNotEqual(seed, derive_path_seed(1729, "G_tok", "prompt-1"))
        self.assertNotEqual(seed, derive_path_seed(1729, "G_bp", "prompt-2"))
        self.assertEqual(
            path_rng(1729, "G_bp", "prompt-1").random(), path_rng(1729, "G_bp", "prompt-1").random()
        )

    def test_invalid_protocol_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluation_partition_domains("cohort", "G_bp", 0)
        with self.assertRaises(ValueError):
            derive_path_seed(-1, "G_bp", "prompt")


if __name__ == "__main__":
    unittest.main()
