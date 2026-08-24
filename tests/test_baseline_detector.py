"""Invariants for the inverse-transform and exponential detectors.

Written before the E8/E9 comparison was run, because a baseline detector that is
quietly weaker than the partition detector would manufacture the conclusion the
comparison is meant to measure.
"""

from __future__ import annotations

import math
import random
import statistics
import unittest

from genomic_watermarks.baselines import (
    EXP_SCHEME,
    ITS_SCHEME,
    KeyedBaselineStream,
    generate_exponential,
    generate_inverse_transform,
    inverse_transform_score,
)
from genomic_watermarks.detector.baseline_search import (
    EXP_NULL_MEAN,
    EXP_NULL_SD,
    ITS_NULL_MEAN,
    ITS_NULL_SD,
    ExponentialScoreCache,
    InverseTransformScoreCache,
    baseline_cache,
    detect_baseline,
    standardized_score,
)
from genomic_watermarks.detector.search import DetectorConfig, PartitionCache, detect
from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.watermark import KeyedPartitionStream, generate_partition_mc

PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/tests/baseline-detector/v1"
PUBLIC_WRONG_KEY = b"genomic-sampling-watermarks/tests/baseline-detector/wrong/v1"
SUPPORT = canonical_kmers()
CONTEXT = "ACGTAC" * 8
STEPS = 48
# One orientation and one phase keeps the search cheap; the shared-enumeration test
# below is what guarantees the full search matches the partition detector.
ALIGNED = DetectorConfig(orientations=("forward",), phases=(0,), stream_offsets=(0,))


def near_uniform_distribution(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """A high-entropy law over the full support, like a real genomic state."""

    weight = 1.0 / len(SUPPORT)
    return SUPPORT, tuple([weight] * len(SUPPORT))


class NullMomentTest(unittest.TestCase):
    def test_the_inverse_transform_null_standard_deviation_is_correct(self) -> None:
        """The declared null sd must match the score's actual null spread."""

        rng = random.Random(11)
        support_size = len(SUPPORT)
        scores = [
            inverse_transform_score(rng.randrange(support_size), support_size, rng.random())
            for _ in range(200_000)
        ]
        self.assertAlmostEqual(statistics.fmean(scores), ITS_NULL_MEAN, delta=0.002)
        self.assertAlmostEqual(statistics.pstdev(scores), ITS_NULL_SD, delta=0.002)

    def test_a_standardized_null_statistic_is_centred_and_unit_scale(self) -> None:
        """Random DNA under a random key must score like a standard normal."""

        rng = random.Random(12)
        for scheme in (ITS_SCHEME, EXP_SCHEME):
            values = []
            for trial in range(60):
                key = f"public-null-{scheme}-{trial}".encode()
                stream = KeyedBaselineStream(key=key, domain="null-moment")
                cache = baseline_cache(scheme, stream, SUPPORT)
                dna = "".join(rng.choice(SUPPORT) for _ in range(STEPS))
                values.append(detect_baseline(dna, ALIGNED, cache, scheme=scheme).statistic)
            with self.subTest(scheme=scheme):
                self.assertLess(abs(statistics.fmean(values)), 0.6)
                self.assertLess(abs(statistics.pstdev(values) - 1.0), 0.5)

    def test_the_exponential_null_moments_are_the_unit_exponential(self) -> None:
        self.assertEqual((EXP_NULL_MEAN, EXP_NULL_SD), (1.0, 1.0))


class RecoveryTest(unittest.TestCase):
    def test_each_baseline_is_recovered_from_dna_and_key_alone(self) -> None:
        """The verifier holds no model, no prompt, and no generation randomness."""

        for scheme, generate in (
            (ITS_SCHEME, generate_inverse_transform),
            (EXP_SCHEME, generate_exponential),
        ):
            stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="recovery")
            result = generate(near_uniform_distribution, CONTEXT, steps=STEPS, stream=stream)
            right = detect_baseline(
                result.dna, ALIGNED, baseline_cache(scheme, stream, SUPPORT), scheme=scheme
            )
            wrong_stream = KeyedBaselineStream(key=PUBLIC_WRONG_KEY, domain="recovery")
            wrong = detect_baseline(
                result.dna, ALIGNED, baseline_cache(scheme, wrong_stream, SUPPORT), scheme=scheme
            )
            with self.subTest(scheme=scheme):
                self.assertGreater(right.statistic, 4.0)
                self.assertLess(wrong.statistic, 3.0)
                self.assertGreater(right.statistic, wrong.statistic)

    def test_recovered_scores_match_the_generator_side_scores(self) -> None:
        """Detector arithmetic must reproduce what generation recorded."""

        for scheme, generate in (
            (ITS_SCHEME, generate_inverse_transform),
            (EXP_SCHEME, generate_exponential),
        ):
            stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="match")
            result = generate(near_uniform_distribution, CONTEXT, steps=STEPS, stream=stream)
            cache = baseline_cache(scheme, stream, SUPPORT)
            recomputed = [cache.score(step.stream_index, step.token) for step in result.steps]
            with self.subTest(scheme=scheme):
                for expected, actual in zip(
                    (step.score for step in result.steps), recomputed, strict=True
                ):
                    self.assertAlmostEqual(expected, actual, places=12)

    def test_a_declared_order_walk_is_marginal_correct_but_undetectable(self) -> None:
        """The invariant that only a detector can catch.

        Walking the cumulative distribution in the declared order instead of the
        keyed order leaves the marginal exactly right and removes the watermark.
        """

        stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="broken")
        rng = random.Random(13)
        tokens = [SUPPORT[int(rng.random() * len(SUPPORT))] for _ in range(STEPS)]
        broken = detect_baseline(
            "".join(tokens),
            ALIGNED,
            baseline_cache(ITS_SCHEME, stream, SUPPORT),
            scheme=ITS_SCHEME,
        )
        self.assertLess(broken.statistic, 3.0)


class SharedSearchTest(unittest.TestCase):
    def test_every_method_searches_the_same_hypothesis_count(self) -> None:
        """A method that searched fewer alignments would get a cheaper threshold."""

        config = DetectorConfig(stream_offsets=(0, 1, 2, 3, 4, 5, 6, 7))
        partition_stream = KeyedPartitionStream(key=PUBLIC_FIXTURE_KEY, domain="shared")
        partition = generate_partition_mc(
            near_uniform_distribution,
            CONTEXT,
            steps=STEPS,
            stream=partition_stream,
            rng=random.Random(14),
        )
        partition_result = detect(
            partition.dna,
            SUPPORT,
            partition_stream,
            config,
            cache=PartitionCache(partition_stream, SUPPORT),
        )
        counts = {"partition": partition_result.hypotheses_searched}
        baseline_stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="shared")
        for scheme, generate in (
            (ITS_SCHEME, generate_inverse_transform),
            (EXP_SCHEME, generate_exponential),
        ):
            result = generate(
                near_uniform_distribution, CONTEXT, steps=STEPS, stream=baseline_stream
            )
            counts[scheme] = detect_baseline(
                result.dna,
                config,
                baseline_cache(scheme, baseline_stream, SUPPORT),
                scheme=scheme,
            ).hypotheses_searched
        self.assertEqual(len(set(counts.values())), 1, counts)
        self.assertEqual(counts["partition"], 2 * 6 * 8)


class CacheTest(unittest.TestCase):
    def test_the_caches_return_the_uncached_values(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="cache")
        exponential = ExponentialScoreCache(stream)
        inverse = InverseTransformScoreCache(stream, SUPPORT)
        for index in (0, 1, 7):
            for token in ("AAAAAA", "ACGTAC", SUPPORT[-1]):
                direct = -math.log1p(-stream.token_uniform(index, token))
                self.assertAlmostEqual(exponential.score(index, token), direct, places=12)
                self.assertAlmostEqual(exponential.score(index, token), direct, places=12)
                permutation = stream.permutation(SUPPORT, index)
                expected = inverse_transform_score(
                    permutation.index(token), len(SUPPORT), stream.uniform(index)
                )
                self.assertAlmostEqual(inverse.score(index, token), expected, places=12)
                self.assertAlmostEqual(inverse.score(index, token), expected, places=12)
        self.assertEqual(inverse.cached_positions, 3)
        self.assertEqual(exponential.cached_entries, 9)


class ValidationTest(unittest.TestCase):
    def test_an_unknown_scheme_is_rejected(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="validate")
        with self.assertRaisesRegex(ValueError, "unknown baseline scheme"):
            baseline_cache("dipmark", stream, SUPPORT)
        with self.assertRaisesRegex(ValueError, "unknown baseline scheme"):
            detect_baseline("ACGTAC" * 20, ALIGNED, ExponentialScoreCache(stream), scheme="dipmark")

    def test_a_token_outside_the_support_is_rejected(self) -> None:
        stream = KeyedBaselineStream(key=PUBLIC_FIXTURE_KEY, domain="validate")
        cache = InverseTransformScoreCache(stream, SUPPORT)
        with self.assertRaisesRegex(ValueError, "outside the declared support"):
            cache.score(0, "NNNNNN")

    def test_standardization_is_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "total must be positive"):
            standardized_score(0.0, 0, null_mean=0.0, null_sd=1.0)
        with self.assertRaisesRegex(ValueError, "standard deviation must be positive"):
            standardized_score(0.0, 4, null_mean=0.0, null_sd=0.0)
        self.assertAlmostEqual(standardized_score(9.0, 9, null_mean=0.0, null_sd=1.0), 3.0)


if __name__ == "__main__":
    unittest.main()
