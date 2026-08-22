"""Invariants for the inverse-transform and exponential baselines.

These were written before the samplers were trusted, and each one targets a
specific way the implementation could be wrong while still looking plausible:
a marginal that drifts, a detector that cannot recompute what the generator did,
a null whose distribution is not what the score assumes, and a deliberately broken
variant that a weak test would pass.
"""

from __future__ import annotations

import math
import random
import statistics
import unittest
from collections import Counter

from genomic_watermarks.baselines import (
    EXP_SCHEME,
    EXPONENTIAL_NULL_MEAN,
    INVERSE_TRANSFORM_NULL_MEAN,
    ITS_SCHEME,
    BaselineResult,
    KeyedBaselineStream,
    exponential_score,
    generate_exponential,
    generate_inverse_transform,
    generate_ordinary_baseline,
    inverse_transform_score,
    sample_exponential,
    sample_inverse_transform,
    score_exponential,
    score_inverse_transform,
)
from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.gof import token_goodness_of_fit

PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v1"
OTHER_PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v2"
ITEMS = canonical_kmers()[:32]
SKEWED = tuple(1.0 / (index + 1) for index in range(32))


def law(weights=None):
    values = weights or tuple([1.0] * len(ITEMS))

    def draw(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return ITEMS, tuple(values)

    return draw


class KeyedBaselineStreamTest(unittest.TestCase):
    def test_uniforms_lie_in_the_unit_interval_and_look_uniform(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="uniform")
        values = [stream.uniform(index) for index in range(4000)]
        self.assertTrue(all(0.0 <= value < 1.0 for value in values))
        self.assertAlmostEqual(statistics.fmean(values), 0.5, delta=0.02)
        self.assertAlmostEqual(statistics.pstdev(values), math.sqrt(1 / 12), delta=0.02)

    def test_token_uniforms_are_independent_across_tokens_and_positions(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="tokens")
        values = [stream.token_uniform(index, token) for index in range(120) for token in ITEMS]
        self.assertAlmostEqual(statistics.fmean(values), 0.5, delta=0.02)
        self.assertNotEqual(stream.token_uniform(0, ITEMS[0]), stream.token_uniform(1, ITEMS[0]))
        self.assertNotEqual(stream.token_uniform(0, ITEMS[0]), stream.token_uniform(0, ITEMS[1]))

    def test_permutation_is_a_reordering_and_position_dependent(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="perm")
        first = stream.permutation(ITEMS, 0)
        self.assertEqual(sorted(first), sorted(ITEMS))
        self.assertEqual(first, stream.permutation(ITEMS, 0))
        self.assertNotEqual(first, stream.permutation(ITEMS, 1))

    def test_streams_are_key_and_domain_separated(self) -> None:
        base = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="a")
        other_domain = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="b")
        other_key = KeyedBaselineStream(key=OTHER_PUBLIC_TEST_KEY, domain="a")
        self.assertNotEqual(base.uniform(0), other_domain.uniform(0))
        self.assertNotEqual(base.uniform(0), other_key.uniform(0))
        self.assertNotEqual(base.permutation(ITEMS, 0), other_key.permutation(ITEMS, 0))

    def test_repr_hides_the_key_and_inputs_are_validated(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="hide")
        self.assertNotIn("public-fixture-key", repr(stream))
        with self.assertRaisesRegex(ValueError, "key must not be empty"):
            KeyedBaselineStream(key=b"", domain="d")
        with self.assertRaisesRegex(ValueError, "domain must not be empty"):
            KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            stream.uniform(-1)


class ExactMarginalTest(unittest.TestCase):
    """The load-bearing invariant: both samplers must reproduce the declared law."""

    def draws(self, generate, trials=60, steps=120, weights=None):
        tokens: list[str] = []
        for trial in range(trials):
            stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain=f"marginal/{trial}")
            tokens.extend(generate(law(weights), "ATCGGC", steps=steps, stream=stream).tokens)
        return tokens

    def test_inverse_transform_preserves_a_skewed_marginal(self) -> None:
        tokens = self.draws(generate_inverse_transform, weights=SKEWED)
        outcome = token_goodness_of_fit(tokens, ITEMS, SKEWED, replicates=400, seed=17)
        self.assertGreater(outcome.p_value, 0.01)

    def test_exponential_preserves_a_skewed_marginal(self) -> None:
        tokens = self.draws(generate_exponential, weights=SKEWED)
        outcome = token_goodness_of_fit(tokens, ITEMS, SKEWED, replicates=400, seed=19)
        self.assertGreater(outcome.p_value, 0.01)

    def test_ignoring_the_permutation_is_invisible_to_the_marginal(self) -> None:
        """A marginal test alone cannot catch this bug; only the detector can.

        Walking the cumulative distribution in the declared order instead of the
        keyed order still emits tokens with exactly the declared frequencies, so a
        goodness-of-fit test passes while the watermark is simply absent. This is
        why distribution preservation is never sufficient evidence on its own.
        """

        tokens: list[str] = []
        for trial in range(60):
            stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain=f"broken/{trial}")
            for index in range(120):
                tokens.append(sample_inverse_transform(ITEMS, SKEWED, ITEMS, stream.uniform(index)))
        counts = Counter(tokens)
        total = sum(SKEWED)
        self.assertAlmostEqual(counts[ITEMS[0]] / len(tokens), SKEWED[0] / total, delta=0.02)

        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="broken-detect")
        broken = [
            sample_inverse_transform(ITEMS, SKEWED, ITEMS, stream.uniform(index))
            for index in range(600)
        ]
        self.assertAlmostEqual(
            statistics.fmean(score_inverse_transform(broken, ITEMS, stream)),
            INVERSE_TRANSFORM_NULL_MEAN,
            delta=0.03,
        )
        correct = generate_inverse_transform(law(SKEWED), "ATCGGC", steps=600, stream=stream)
        self.assertGreater(
            statistics.fmean(score_inverse_transform(correct.tokens, ITEMS, stream)),
            INVERSE_TRANSFORM_NULL_MEAN + 0.05,
        )

    def test_a_broken_exponential_is_caught_by_the_marginal(self) -> None:
        """Dropping the 1/p exponent turns the sampler into an argmax over uniforms."""

        tokens: list[str] = []
        for trial in range(40):
            stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain=f"brokenexp/{trial}")
            for index in range(120):
                uniforms = [stream.token_uniform(index, token) for token in ITEMS]
                tokens.append(max(zip(ITEMS, uniforms, strict=True), key=lambda pair: pair[1])[0])
        outcome = token_goodness_of_fit(tokens, ITEMS, SKEWED, replicates=200, seed=23)
        self.assertLess(outcome.p_value, 0.01)


class DetectorRecomputationTest(unittest.TestCase):
    """The verifier must reproduce the generator's scores from DNA and the key alone."""

    def test_inverse_transform_scores_are_recomputable(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="recompute-its")
        result = generate_inverse_transform(law(SKEWED), "ATCGGC", steps=40, stream=stream)
        recovered = score_inverse_transform(result.tokens, ITEMS, stream)
        for step, value in zip(result.steps, recovered, strict=True):
            self.assertAlmostEqual(step.score, value)

    def test_exponential_scores_are_recomputable(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="recompute-exp")
        result = generate_exponential(law(SKEWED), "ATCGGC", steps=40, stream=stream)
        recovered = score_exponential(result.tokens, ITEMS, stream)
        for step, value in zip(result.steps, recovered, strict=True):
            self.assertAlmostEqual(step.score, value)

    def test_offsets_shift_both_streams(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="offset")
        result = generate_exponential(law(), "ATCGGC", steps=20, stream=stream, stream_offset=13)
        self.assertEqual([s.stream_index for s in result.steps], list(range(13, 33)))
        recovered = score_exponential(result.tokens, ITEMS, stream, stream_offset=13)
        self.assertAlmostEqual(math.fsum(recovered), result.total_score)

    def test_recomputation_validates_inputs(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="validate")
        with self.assertRaisesRegex(ValueError, "tokens must not be empty"):
            score_exponential((), ITEMS, stream)
        with self.assertRaisesRegex(ValueError, "support is missing"):
            score_inverse_transform(("TTTTTT",), ITEMS, stream)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            score_exponential((ITEMS[0],), ITEMS, stream, stream_offset=-1)


class NullDistributionTest(unittest.TestCase):
    """Each score's null must be what its detector assumes, or calibration is wrong."""

    def wrong_key_scores(self, generate, scorer, steps=600):
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="null")
        result = generate(law(), "ATCGGC", steps=steps, stream=stream)
        wrong = KeyedBaselineStream(key=OTHER_PUBLIC_TEST_KEY, domain="null")
        return scorer(result.tokens, ITEMS, wrong)

    def test_exponential_null_is_a_unit_exponential(self) -> None:
        scores = self.wrong_key_scores(generate_exponential, score_exponential)
        self.assertAlmostEqual(statistics.fmean(scores), EXPONENTIAL_NULL_MEAN, delta=0.15)
        # A unit exponential has variance one as well as mean one.
        self.assertAlmostEqual(statistics.pvariance(scores), 1.0, delta=0.35)

    def test_inverse_transform_null_is_centred_on_zero(self) -> None:
        scores = self.wrong_key_scores(generate_inverse_transform, score_inverse_transform)
        self.assertAlmostEqual(statistics.fmean(scores), INVERSE_TRANSFORM_NULL_MEAN, delta=0.02)

    def test_ordinary_generation_scores_like_the_null(self) -> None:
        ordinary = generate_ordinary_baseline(law(), "ATCGGC", steps=600, rng=random.Random(5))
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="ordinary")
        self.assertAlmostEqual(
            statistics.fmean(score_exponential(ordinary.tokens, ITEMS, stream)),
            EXPONENTIAL_NULL_MEAN,
            delta=0.15,
        )
        self.assertAlmostEqual(
            statistics.fmean(score_inverse_transform(ordinary.tokens, ITEMS, stream)),
            INVERSE_TRANSFORM_NULL_MEAN,
            delta=0.02,
        )


class SignalTest(unittest.TestCase):
    def test_the_correct_key_scores_far_above_its_null(self) -> None:
        for generate, scorer, null in (
            (generate_exponential, score_exponential, EXPONENTIAL_NULL_MEAN),
            (generate_inverse_transform, score_inverse_transform, INVERSE_TRANSFORM_NULL_MEAN),
        ):
            stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="signal")
            result = generate(law(), "ATCGGC", steps=400, stream=stream)
            correct = statistics.fmean(scorer(result.tokens, ITEMS, stream))
            wrong = statistics.fmean(
                scorer(
                    result.tokens,
                    ITEMS,
                    KeyedBaselineStream(key=OTHER_PUBLIC_TEST_KEY, domain="signal"),
                )
            )
            self.assertGreater(correct, null)
            self.assertGreater(correct, wrong)

    def test_generation_is_deterministic_given_the_key(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="replay")
        first = generate_exponential(law(SKEWED), "ATCGGC", steps=30, stream=stream)
        second = generate_exponential(law(SKEWED), "ATCGGC", steps=30, stream=stream)
        self.assertEqual(first.tokens, second.tokens)
        third = generate_inverse_transform(law(SKEWED), "ATCGGC", steps=30, stream=stream)
        fourth = generate_inverse_transform(law(SKEWED), "ATCGGC", steps=30, stream=stream)
        self.assertEqual(third.tokens, fourth.tokens)


class PrimitiveTest(unittest.TestCase):
    def test_inverse_transform_selects_by_cumulative_mass(self) -> None:
        items = ("a", "b", "c")
        probabilities = (0.5, 0.3, 0.2)
        self.assertEqual(sample_inverse_transform(items, probabilities, items, 0.0), "a")
        self.assertEqual(sample_inverse_transform(items, probabilities, items, 0.49), "a")
        self.assertEqual(sample_inverse_transform(items, probabilities, items, 0.5), "b")
        self.assertEqual(sample_inverse_transform(items, probabilities, items, 0.99), "c")
        reordered = ("c", "b", "a")
        self.assertEqual(sample_inverse_transform(items, probabilities, reordered, 0.1), "c")

    def test_exponential_never_selects_a_zero_probability_token(self) -> None:
        items = ("a", "b", "c")
        probabilities = (0.0, 0.5, 0.5)
        for uniform in (0.999999, 0.5, 0.000001):
            chosen = sample_exponential(items, probabilities, (0.999999, uniform, uniform))
            self.assertNotEqual(chosen, "a")

    def test_primitives_validate_their_inputs(self) -> None:
        items = ("a", "b")
        with self.assertRaisesRegex(ValueError, r"uniform must lie in \[0, 1\)"):
            sample_inverse_transform(items, (0.5, 0.5), items, 1.0)
        with self.assertRaisesRegex(ValueError, "reordering of the items"):
            sample_inverse_transform(items, (0.5, 0.5), ("a", "a"), 0.1)
        with self.assertRaisesRegex(ValueError, "same length"):
            sample_exponential(items, (0.5, 0.5), (0.1,))
        with self.assertRaisesRegex(ValueError, r"lie in \[0, 1\)"):
            sample_exponential(items, (0.5, 0.5), (0.1, 1.0))
        with self.assertRaisesRegex(ValueError, "support size must be positive"):
            inverse_transform_score(0, 0, 0.5)
        with self.assertRaisesRegex(ValueError, r"rank must lie in \[0, support size\)"):
            inverse_transform_score(5, 4, 0.5)
        with self.assertRaisesRegex(ValueError, r"uniform must lie in \[0, 1\)"):
            exponential_score(1.0)

    def test_result_summaries(self) -> None:
        empty = BaselineResult(scheme=ITS_SCHEME, tokens=("ATCGGC",), steps=())
        self.assertEqual(empty.mean_score, 0.0)
        self.assertEqual(empty.dna, "ATCGGC")
        stream = KeyedBaselineStream(key=PUBLIC_TEST_KEY, domain="summary")
        result = generate_exponential(law(), "ATCGGC", steps=10, stream=stream)
        self.assertEqual(result.scheme, EXP_SCHEME)
        self.assertAlmostEqual(result.mean_score, result.total_score / 10)


if __name__ == "__main__":
    unittest.main()
