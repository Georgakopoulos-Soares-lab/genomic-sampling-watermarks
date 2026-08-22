from __future__ import annotations

import math
import random
import unittest

from genomic_watermarks.detector.search import (
    FORWARD,
    REVERSE_COMPLEMENT,
    DetectorConfig,
    WindowedSearchConfig,
    calibrate_threshold,
    detect,
    detect_windowed,
)
from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.edits import delete_bases
from genomic_watermarks.watermark import (
    KeyedPartitionStream,
    generate_ordinary,
    generate_partition_mc,
)

PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v1"
OTHER_PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v2"
SUPPORT = canonical_kmers()


def uniform(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
    return SUPPORT, tuple([1.0] * len(SUPPORT))


def watermarked(domain: str, *, steps: int, seed: int) -> str:
    stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=domain)
    return generate_partition_mc(
        uniform, "ATCGGC", steps=steps, stream=stream, rng=random.Random(seed)
    ).dna


class WindowedSearchConfigTest(unittest.TestCase):
    def test_starts_use_a_half_window_stride_and_skip_oversized_windows(self) -> None:
        config = WindowedSearchConfig(window_tokens=(32, 64), drift_offsets=(0,))
        self.assertEqual(config.window_starts(64, 32), (0, 16, 32))
        self.assertEqual(config.window_starts(64, 64), (0,))
        self.assertEqual(config.window_starts(16, 32), ())

    def test_hypothesis_count_is_computed_per_phase(self) -> None:
        config = WindowedSearchConfig(
            orientations=(FORWARD,), phases=(0,), window_tokens=(32,), drift_offsets=(0, 1)
        )
        # 384 bases at phase 0 is 64 tokens; window 32, stride 16 -> starts 0, 16, 32.
        self.assertEqual(config.hypothesis_count(384), 6)
        # Phase 1 drops the trailing partial k-mer, leaving 63 tokens and two starts.
        shifted = WindowedSearchConfig(
            orientations=(FORWARD,), phases=(1,), window_tokens=(32,), drift_offsets=(0, 1)
        )
        self.assertEqual(shifted.hypothesis_count(384), 4)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            config.hypothesis_count(-1)

    def test_config_rejects_malformed_searches(self) -> None:
        for kwargs, message in (
            ({"orientations": ()}, "at least one orientation"),
            ({"phases": (9,)}, r"phases must lie in \[0, 5\]"),
            ({"window_tokens": ()}, "at least one window length"),
            ({"window_tokens": (1,)}, "at least two tokens"),
            ({"window_tokens": (32, 32)}, "window lengths must be unique"),
            ({"drift_offsets": ()}, "at least one drift offset"),
            ({"drift_offsets": (0, 0)}, "drift offsets must be unique"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                WindowedSearchConfig(**kwargs)

    def test_signed_drift_is_allowed_and_negative_key_starts_are_skipped(self) -> None:
        """Insertions need negative drift; a non-negative-only range cannot reach them."""

        config = WindowedSearchConfig(
            orientations=(FORWARD,), phases=(0,), window_tokens=(32,), drift_offsets=(-2, 0)
        )
        # 64 tokens, window 32, stride 16 -> starts 0, 16, 32. Drift -2 is unscorable at start 0.
        self.assertEqual(config.hypothesis_count(384), 5)

    def test_a_window_recovers_a_segment_after_an_insertion(self) -> None:
        """Seven insertions exceed what a phase shift can absorb, so drift must go negative."""

        sequence = watermarked("win-ins", steps=64, seed=7)
        edited = sequence[:96] + "A" * 7 + sequence[96:]
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-ins")
        positive_only = WindowedSearchConfig(window_tokens=(32,), drift_offsets=(0, 1))
        signed = WindowedSearchConfig(window_tokens=(32,), drift_offsets=(-1, 0, 1))
        # Without a negative drift the post-insertion segment is unreachable.
        self.assertLess(detect_windowed(edited, SUPPORT, stream, positive_only).statistic, 5.0)
        recovered = detect_windowed(edited, SUPPORT, stream, signed)
        self.assertEqual(recovered.matches, recovered.total)
        self.assertEqual(recovered.hypothesis.drift, -1)
        self.assertGreater(recovered.hypothesis.window_start, 0)

    def test_describe_states_the_key_position_rule(self) -> None:
        described = WindowedSearchConfig().describe()
        self.assertEqual(described["kind"], "windowed")
        self.assertTrue(described["drift_is_signed"])
        self.assertIn("signed drift", str(described["key_position_rule"]))


class DetectWindowedTest(unittest.TestCase):
    def test_clean_sequence_is_found_at_the_origin_alignment(self) -> None:
        sequence = watermarked("win-clean", steps=64, seed=1)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-clean")
        config = WindowedSearchConfig(window_tokens=(32, 64), drift_offsets=(0, 1))
        result = detect_windowed(sequence, SUPPORT, stream, config)
        self.assertEqual(result.matches, result.total)
        self.assertEqual(result.hypothesis.drift, 0)
        self.assertEqual(result.hypothesis.orientation, FORWARD)
        self.assertEqual(result.hypothesis.phase, 0)
        self.assertAlmostEqual(result.statistic, math.sqrt(result.total))
        self.assertEqual(result.hypotheses_searched, config.hypothesis_count(len(sequence)))

    def test_a_window_recovers_a_segment_after_a_deletion(self) -> None:
        """A deletion the unwindowed search dilutes away is recovered by a window."""

        sequence = watermarked("win-del", steps=64, seed=2)
        # Delete one base a quarter of the way in, so the aligned suffix is three
        # quarters of the sequence but the prefix is only a quarter.
        edited = sequence[:96] + sequence[97:]
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-del")
        config = WindowedSearchConfig(window_tokens=(32,), drift_offsets=(0, 1))
        result = detect_windowed(edited, SUPPORT, stream, config)
        self.assertEqual(result.matches, result.total)
        self.assertEqual(result.total, 32)
        # The recovered window sits after the deletion and needs a drift of one.
        self.assertEqual(result.hypothesis.drift, 1)
        self.assertGreater(result.hypothesis.window_start, 0)

    def test_windowing_beats_the_unwindowed_search_on_a_fragmented_read(self) -> None:
        sequence = watermarked("win-frag", steps=256, seed=3)
        edited = delete_bases(sequence, 0.01, random.Random(11))
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-frag")
        unwindowed = detect(edited, SUPPORT, stream, DetectorConfig(stream_offsets=tuple(range(8))))
        windowed = detect_windowed(
            edited,
            SUPPORT,
            stream,
            WindowedSearchConfig(window_tokens=(32, 64), drift_offsets=tuple(range(8))),
        )
        self.assertGreater(windowed.statistic, unwindowed.statistic)

    def test_reverse_complement_is_recovered(self) -> None:
        from genomic_watermarks.dna import reverse_complement

        sequence = watermarked("win-rc", steps=64, seed=4)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-rc")
        result = detect_windowed(
            reverse_complement(sequence),
            SUPPORT,
            stream,
            WindowedSearchConfig(window_tokens=(32,), drift_offsets=(0,)),
        )
        self.assertEqual(result.hypothesis.orientation, REVERSE_COMPLEMENT)
        self.assertEqual(result.matches, result.total)

    def test_wrong_key_and_ordinary_generation_stay_near_chance(self) -> None:
        sequence = watermarked("win-null", steps=64, seed=5)
        config = WindowedSearchConfig(window_tokens=(32,), drift_offsets=(0, 1))
        wrong = KeyedPartitionStream(key=OTHER_PUBLIC_TEST_KEY, domain="win-null")
        self.assertLess(detect_windowed(sequence, SUPPORT, wrong, config).statistic, 5.0)
        ordinary = generate_ordinary(uniform, "ATCGGC", steps=64, rng=random.Random(6)).dna
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-null")
        self.assertLess(detect_windowed(ordinary, SUPPORT, stream, config).statistic, 5.0)

    def test_a_sequence_too_short_for_any_window_is_rejected(self) -> None:
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="win-short")
        config = WindowedSearchConfig(window_tokens=(64,), drift_offsets=(0,))
        with self.assertRaisesRegex(ValueError, "scored no hypothesis"):
            detect_windowed("ATCGGC" * 4, SUPPORT, stream, config)

    def test_windowed_nulls_calibrate_and_separate(self) -> None:
        config = WindowedSearchConfig(window_tokens=(32,), drift_offsets=(0, 1))
        nulls = []
        for trial in range(20):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"win-cal/{trial}")
            ordinary = generate_ordinary(
                uniform, "ATCGGC", steps=64, rng=random.Random(500 + trial)
            ).dna
            nulls.append(detect_windowed(ordinary, SUPPORT, stream, config).statistic)
        calibration = calibrate_threshold(nulls, 0.10)
        positives = []
        for trial in range(6):
            domain = f"win-pos/{trial}"
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=domain)
            positives.append(
                detect_windowed(
                    watermarked(domain, steps=64, seed=600 + trial), SUPPORT, stream, config
                ).statistic
            )
        self.assertGreater(min(positives), max(nulls))
        self.assertGreater(min(positives), calibration.threshold)


if __name__ == "__main__":
    unittest.main()
