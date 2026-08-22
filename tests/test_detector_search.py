from __future__ import annotations

import math
import random
import unittest

from genomic_watermarks.detector.search import (
    FORWARD,
    REVERSE_COMPLEMENT,
    DetectorConfig,
    PartitionCache,
    calibrate_threshold,
    detect,
    detect_aligned,
    detection_rate,
    empirical_p_value,
    enumerate_search,
    standardized_agreement,
)
from genomic_watermarks.dna import canonical_kmers, reverse_complement, tokenize_fixed
from genomic_watermarks.watermark import (
    KeyedPartitionStream,
    generate_ordinary,
    generate_partition_mc,
)

PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v1"
OTHER_PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v2"
SUPPORT = canonical_kmers()


def uniform_distribution(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """A uniform law over the complete support, so the partition mass is exactly one half.

    Maximal coupling then agrees with the latent bit at every position, which makes the
    correctness assertions below exact rather than statistical.
    """

    return SUPPORT, tuple([1.0] * len(SUPPORT))


def watermarked_dna(domain: str, *, steps: int, seed: int, offset: int = 0) -> str:
    stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=domain)
    return generate_partition_mc(
        uniform_distribution,
        "ATCGGC",
        steps=steps,
        stream=stream,
        rng=random.Random(seed),
        stream_offset=offset,
    ).dna


def ordinary_dna(*, steps: int, seed: int) -> str:
    return generate_ordinary(
        uniform_distribution, "ATCGGC", steps=steps, rng=random.Random(seed)
    ).dna


class StandardizedAgreementTest(unittest.TestCase):
    def test_statistic_is_zero_at_chance_and_scales_with_length(self) -> None:
        self.assertAlmostEqual(standardized_agreement(50, 100), 0.0)
        self.assertAlmostEqual(standardized_agreement(100, 100), 10.0)
        self.assertAlmostEqual(standardized_agreement(0, 100), -10.0)
        self.assertAlmostEqual(standardized_agreement(400, 400), 20.0)

    def test_statistic_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "total must be positive"):
            standardized_agreement(0, 0)
        with self.assertRaisesRegex(ValueError, r"matches must lie in \[0, total\]"):
            standardized_agreement(5, 4)


class DetectorConfigTest(unittest.TestCase):
    def test_default_config_describes_the_twelve_alignment_hypotheses(self) -> None:
        config = DetectorConfig()
        described = config.describe()
        self.assertEqual(described["orientations"], [FORWARD, REVERSE_COMPLEMENT])
        self.assertEqual(described["phases"], [0, 1, 2, 3, 4, 5])
        self.assertEqual(described["window_tokens"], "full_sequence_only")
        self.assertEqual(described["stream_offsets"], [0])

    def test_config_rejects_malformed_searches(self) -> None:
        for kwargs, message in (
            ({"orientations": ()}, "at least one orientation"),
            ({"orientations": ("sideways",)}, "unknown orientation"),
            ({"orientations": (FORWARD, FORWARD)}, "orientations must be unique"),
            ({"phases": ()}, "at least one phase"),
            ({"phases": (0, 6)}, r"phases must lie in \[0, 5\]"),
            ({"phases": (0, 0)}, "phases must be unique"),
            ({"window_tokens": (0,)}, "window lengths must be positive"),
            ({"window_tokens": (8, 8)}, "window lengths must be unique"),
            ({"window_tokens": (8,)}, "positive stride is required"),
            ({"stream_offsets": ()}, "at least one key-stream offset"),
            ({"stream_offsets": (-1,)}, "offsets must be non-negative"),
            ({"stream_offsets": (0, 0)}, "offsets must be unique"),
            ({"minimum_window_tokens": 0}, "minimum_window_tokens must be positive"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                DetectorConfig(**kwargs)


class EnumerateSearchTest(unittest.TestCase):
    def test_hypothesis_count_matches_the_declared_search(self) -> None:
        sequence = watermarked_dna("enumerate", steps=24, seed=1)
        config = DetectorConfig(stream_offsets=(0, 1, 2))
        enumerated = enumerate_search(sequence, config)
        self.assertEqual(len(enumerated), 2 * 6 * 1 * 3)

    def test_declared_windows_add_hypotheses_and_respect_the_stride(self) -> None:
        sequence = watermarked_dna("windows", steps=64, seed=2)
        config = DetectorConfig(
            orientations=(FORWARD,),
            phases=(0,),
            window_tokens=(32,),
            window_stride_tokens=16,
        )
        enumerated = enumerate_search(sequence, config)
        starts = sorted({hypothesis.window_start for hypothesis, _ in enumerated})
        lengths = sorted({hypothesis.window_tokens for hypothesis, _ in enumerated})
        self.assertEqual(lengths, [32, 64])
        self.assertEqual(starts, [0, 16, 32])
        self.assertEqual(len(enumerated), 4)

    def test_short_sequences_and_short_windows_are_skipped(self) -> None:
        short = watermarked_dna("short", steps=4, seed=3)
        self.assertEqual(enumerate_search(short, DetectorConfig()), ())
        sequence = watermarked_dna("skip", steps=64, seed=4)
        config = DetectorConfig(
            orientations=(FORWARD,),
            phases=(0,),
            window_tokens=(4, 512),
            window_stride_tokens=8,
        )
        enumerated = enumerate_search(sequence, config)
        self.assertEqual({hypothesis.window_tokens for hypothesis, _ in enumerated}, {64})

    def test_reverse_complement_hypotheses_read_the_other_strand(self) -> None:
        sequence = watermarked_dna("strand", steps=24, seed=5)
        config = DetectorConfig(orientations=(REVERSE_COMPLEMENT,), phases=(0,))
        ((_, tokens),) = enumerate_search(sequence, config)
        self.assertEqual(tokens, tokenize_fixed(reverse_complement(sequence)))


class DetectTest(unittest.TestCase):
    def test_aligned_check_recovers_a_perfect_uniform_state_signal(self) -> None:
        sequence = watermarked_dna("aligned", steps=24, seed=6)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="aligned")
        result = detect_aligned(tokenize_fixed(sequence), SUPPORT, stream)
        self.assertEqual(result.matches, 24)
        self.assertEqual(result.total, 24)
        self.assertEqual(result.hypotheses_searched, 1)
        self.assertAlmostEqual(result.agreement_rate, 1.0)
        self.assertAlmostEqual(result.statistic, math.sqrt(24))

    def test_full_search_finds_the_true_alignment(self) -> None:
        sequence = watermarked_dna("search", steps=24, seed=7)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="search")
        result = detect(sequence, SUPPORT, stream, DetectorConfig())
        self.assertEqual(result.hypothesis.orientation, FORWARD)
        self.assertEqual(result.hypothesis.phase, 0)
        self.assertEqual(result.hypothesis.stream_offset, 0)
        self.assertEqual(result.matches, result.total)
        self.assertEqual(result.hypotheses_searched, 12)

    def test_full_search_recovers_a_shifted_key_stream(self) -> None:
        sequence = watermarked_dna("shifted", steps=24, seed=8, offset=17)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="shifted")
        config = DetectorConfig(stream_offsets=tuple(range(0, 24)))
        result = detect(sequence, SUPPORT, stream, config)
        self.assertEqual(result.hypothesis.stream_offset, 17)
        self.assertEqual(result.matches, result.total)

    def test_full_search_recovers_a_reverse_complemented_sequence(self) -> None:
        sequence = watermarked_dna("rc", steps=24, seed=9)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="rc")
        stored = reverse_complement(sequence)
        result = detect(stored, SUPPORT, stream, DetectorConfig())
        self.assertEqual(result.hypothesis.orientation, REVERSE_COMPLEMENT)
        self.assertEqual(result.matches, result.total)

    def test_wrong_key_stays_near_chance(self) -> None:
        sequence = watermarked_dna("wrongkey", steps=64, seed=10)
        wrong = KeyedPartitionStream(key=OTHER_PUBLIC_TEST_KEY, domain="wrongkey")
        result = detect(sequence, SUPPORT, wrong, DetectorConfig())
        self.assertLess(result.statistic, 4.0)
        self.assertLess(result.agreement_rate, 0.65)

    def test_ordinary_generation_stays_near_chance(self) -> None:
        sequence = ordinary_dna(steps=64, seed=11)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="ordinary-null")
        result = detect(sequence, SUPPORT, stream, DetectorConfig())
        self.assertLess(result.statistic, 4.0)

    def test_search_rejects_sequences_it_cannot_score(self) -> None:
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="tooshort")
        with self.assertRaisesRegex(ValueError, "scored no hypothesis"):
            detect("ATCGGC", SUPPORT, stream, DetectorConfig())
        with self.assertRaisesRegex(ValueError, "tokens must not be empty"):
            detect_aligned((), SUPPORT, stream)

    def test_cache_is_reused_across_hypotheses(self) -> None:
        sequence = watermarked_dna("cache", steps=24, seed=12)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="cache")
        cache = PartitionCache(stream, SUPPORT)
        config = DetectorConfig(stream_offsets=(0, 1))
        detect(sequence, SUPPORT, stream, config, cache=cache)
        # 12 alignment hypotheses read at most 24 positions from two offsets.
        self.assertLessEqual(cache.cached_positions, 26)
        self.assertGreater(cache.cached_positions, 0)
        with self.assertRaisesRegex(ValueError, "outside the declared support"):
            cache.agrees(0, "NNNNNN")
        with self.assertRaisesRegex(ValueError, "support must not be empty"):
            PartitionCache(stream, ())


class CalibrationTest(unittest.TestCase):
    def test_threshold_meets_the_target_and_reports_what_it_achieved(self) -> None:
        nulls = [float(value) for value in range(100)]
        calibration = calibrate_threshold(nulls, 0.05)
        self.assertLessEqual(calibration.achieved_false_positive_rate, 0.05)
        self.assertEqual(calibration.null_trials, 100)
        self.assertAlmostEqual(calibration.attainable_false_positive_rate, 0.01)
        self.assertTrue(calibration.is_attainable)
        # The decision rule and the calibration must count exceedances the same way.
        self.assertAlmostEqual(
            detection_rate(nulls, calibration.threshold),
            calibration.achieved_false_positive_rate,
        )

    def test_ties_at_the_threshold_are_not_counted_as_detections(self) -> None:
        """The statistic is discrete, so ties at a null-order-statistic threshold are common."""

        nulls = [1.0] * 50 + [2.0] * 40 + [3.0] * 10
        calibration = calibrate_threshold(nulls, 0.10)
        self.assertEqual(calibration.threshold, 2.0)
        self.assertAlmostEqual(calibration.achieved_false_positive_rate, 0.10)
        self.assertAlmostEqual(
            detection_rate(nulls, calibration.threshold),
            calibration.achieved_false_positive_rate,
        )
        self.assertAlmostEqual(detection_rate([2.0], calibration.threshold), 0.0)
        self.assertAlmostEqual(detection_rate([3.0], calibration.threshold), 1.0)

    def test_unattainable_targets_are_flagged_not_hidden(self) -> None:
        calibration = calibrate_threshold([1.0, 2.0, 3.0], 0.001)
        self.assertFalse(calibration.is_attainable)
        self.assertAlmostEqual(calibration.attainable_false_positive_rate, 1 / 3)
        self.assertEqual(calibration.achieved_false_positive_rate, 0.0)
        self.assertEqual(calibration.threshold, 3.0)

    def test_calibration_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one trial"):
            calibrate_threshold([], 0.05)
        with self.assertRaisesRegex(ValueError, "must lie in"):
            calibrate_threshold([1.0], 0.0)

    def test_empirical_p_value_is_bounded_and_monotone(self) -> None:
        nulls = [0.0, 1.0, 2.0, 3.0]
        self.assertAlmostEqual(empirical_p_value(10.0, nulls), 1 / 5)
        self.assertAlmostEqual(empirical_p_value(-1.0, nulls), 5 / 5)
        self.assertGreater(empirical_p_value(1.5, nulls), empirical_p_value(2.5, nulls))
        with self.assertRaisesRegex(ValueError, "at least one null trial"):
            empirical_p_value(1.0, [])

    def test_detection_rate_validates_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one trial"):
            detection_rate([], 1.0)


class EndToEndCalibrationTest(unittest.TestCase):
    def test_calibrated_search_separates_watermarked_from_null_sequences(self) -> None:
        config = DetectorConfig(stream_offsets=(0, 1, 2, 3))
        null_statistics: list[float] = []
        for trial in range(20):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"cal/{trial}")
            sequence = ordinary_dna(steps=24, seed=1000 + trial)
            null_statistics.append(detect(sequence, SUPPORT, stream, config).statistic)
        calibration = calibrate_threshold(null_statistics, 0.10)

        positive_statistics: list[float] = []
        for trial in range(6):
            domain = f"cal-positive/{trial}"
            sequence = watermarked_dna(domain, steps=24, seed=2000 + trial)
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=domain)
            positive_statistics.append(detect(sequence, SUPPORT, stream, config).statistic)

        self.assertEqual(detection_rate(positive_statistics, calibration.threshold), 1.0)
        self.assertGreater(min(positive_statistics), max(null_statistics))
        for statistic in positive_statistics:
            self.assertAlmostEqual(empirical_p_value(statistic, null_statistics), 1 / 21)
        self.assertTrue(all(math.isfinite(value) for value in null_statistics))


if __name__ == "__main__":
    unittest.main()
