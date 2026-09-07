from __future__ import annotations

import unittest

from genomic_watermarks.models.base import ContinuationLikelihood, DistributionState


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

    def test_continuation_likelihood_validates_public_summary(self) -> None:
        result = ContinuationLikelihood(
            token_count=2,
            negative_log_likelihood=1.0,
            mean_negative_log_likelihood=0.5,
            perplexity=1.6487212707,
        )
        self.assertEqual(result.token_count, 2)
        with self.assertRaisesRegex(ValueError, "token_count"):
            ContinuationLikelihood(
                token_count=0,
                negative_log_likelihood=0.0,
                mean_negative_log_likelihood=0.0,
                perplexity=1.0,
            )


if __name__ == "__main__":
    unittest.main()
