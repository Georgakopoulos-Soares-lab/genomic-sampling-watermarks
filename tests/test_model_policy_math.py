from __future__ import annotations

import unittest

from genomic_watermarks.models.policy_math import apply_generation_policy, canonical_softmax


class DirectTokenPolicyMathTest(unittest.TestCase):
    def test_canonical_softmax_masks_and_normalizes(self) -> None:
        self.assertEqual(canonical_softmax((100.0, 0.0, -100.0, 0.0), (1, 3)), (0.5, 0.5))

    def test_only_retained_direct_token_policies_are_accepted(self) -> None:
        tokens = ("AAAAAA", "TTTTTT")
        self.assertEqual(apply_generation_policy("C_tok", tokens, (8, 2)), (0.8, 0.2))
        self.assertEqual(apply_generation_policy("G_tok", tokens, (8, 2)), (0.8, 0.2))
        with self.assertRaises(ValueError):
            apply_generation_policy("removed_policy", tokens, (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()
