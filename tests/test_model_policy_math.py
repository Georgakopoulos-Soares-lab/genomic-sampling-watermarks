from __future__ import annotations

import math
import unittest

from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.models.policy_math import (
    apply_generation_policy,
    base_marginals,
    canonical_softmax,
    independent_base_product_distribution,
    product_distribution_from_base_marginals,
)


class ModelPolicyMathTest(unittest.TestCase):
    def test_canonical_softmax_masks_and_normalizes(self) -> None:
        probabilities = canonical_softmax((100.0, 0.0, -100.0, 0.0), (1, 3))
        self.assertEqual(probabilities, (0.5, 0.5))

    def test_base_product_breaks_cross_position_correlation(self) -> None:
        tokens = canonical_kmers(2)
        probabilities = [0.0] * len(tokens)
        probabilities[tokens.index("AA")] = 0.5
        probabilities[tokens.index("TT")] = 0.5

        marginals = base_marginals(tokens, probabilities, k=2)
        self.assertEqual(marginals[0], (0.5, 0.5, 0.0, 0.0))
        self.assertEqual(marginals[1], (0.5, 0.5, 0.0, 0.0))

        product = independent_base_product_distribution(tokens, probabilities, k=2)
        for token in ("AA", "AT", "TA", "TT"):
            self.assertAlmostEqual(product[tokens.index(token)], 0.25)
        self.assertAlmostEqual(math.fsum(product), 1.0)

    def test_declared_policy_transform(self) -> None:
        tokens = canonical_kmers(2)
        probabilities = tuple(1.0 if token == "AA" else 0.0 for token in tokens)
        self.assertEqual(apply_generation_policy("G_tok", tokens, probabilities), probabilities)
        self.assertEqual(apply_generation_policy("G_bp", tokens, probabilities), probabilities)
        with self.assertRaises(ValueError):
            apply_generation_policy("C_deployed", tokens, probabilities)

    def test_product_distribution_accepts_explicit_base_marginals(self) -> None:
        tokens = canonical_kmers(2)
        product = product_distribution_from_base_marginals(
            tokens,
            ((0.75, 0.25, 0.0, 0.0), (0.5, 0.5, 0.0, 0.0)),
            k=2,
        )
        self.assertAlmostEqual(product[tokens.index("AA")], 0.375)
        self.assertAlmostEqual(product[tokens.index("AT")], 0.375)
        self.assertAlmostEqual(product[tokens.index("TA")], 0.125)
        self.assertAlmostEqual(product[tokens.index("TT")], 0.125)

    def test_product_distribution_rejects_wrong_marginal_shape(self) -> None:
        with self.assertRaises(ValueError):
            product_distribution_from_base_marginals(canonical_kmers(2), ((1.0, 0.0),), k=2)


if __name__ == "__main__":
    unittest.main()
