from __future__ import annotations

import unittest

from genomic_watermarks.models.base import DistributionState


class DistributionStateTest(unittest.TestCase):
    def test_accepts_normalized_distribution(self) -> None:
        state = DistributionState(
            tokens=("AAAAAA", "TTTTTT"),
            probabilities=(0.25, 0.75),
            metadata={"policy_id": "test"},
        )
        self.assertEqual(state.probabilities, (0.25, 0.75))

    def test_rejects_invalid_distribution(self) -> None:
        with self.assertRaises(ValueError):
            DistributionState(tokens=("AAAAAA",), probabilities=(0.9,), metadata={})
        with self.assertRaises(ValueError):
            DistributionState(
                tokens=("AAAAAA", "AAAAAA"),
                probabilities=(0.5, 0.5),
                metadata={},
            )


if __name__ == "__main__":
    unittest.main()
