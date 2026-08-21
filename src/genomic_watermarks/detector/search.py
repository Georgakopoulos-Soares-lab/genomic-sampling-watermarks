"""The standalone detector: a declared hypothesis search and empirical calibration.

The verifier receives DNA, a runtime key, and public configuration. It has no
model, no prompt, no logits, no generation seed, and no reference sequence.

For one aligned hypothesis the statistic is the standardized keyed group
agreement

``z = (2 * matches - total) / sqrt(total)``

which is asymptotically standard normal under the null that each observed token's
keyed group is an independent fair coin. The detector reports the maximum ``z``
over the complete declared search, so the reported value is not a per-hypothesis
statistic and its nominal normal tail is not a p-value. A p-value only comes from
null trials that repeat the identical search.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from genomic_watermarks.dna import KMER_SIZE, normalize_dna, reverse_complement, tokenize_fixed
from genomic_watermarks.watermark import KeyedPartitionStream

FORWARD = "forward"
REVERSE_COMPLEMENT = "reverse_complement"
ORIENTATIONS = (FORWARD, REVERSE_COMPLEMENT)


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    """The complete declared search. Null calibration must reuse it unchanged."""

    orientations: tuple[str, ...] = ORIENTATIONS
    phases: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    window_tokens: tuple[int, ...] = ()
    window_stride_tokens: int = 0
    stream_offsets: tuple[int, ...] = (0,)
    minimum_window_tokens: int = 16

    def __post_init__(self) -> None:
        if not self.orientations:
            raise ValueError("at least one orientation must be searched")
        if any(orientation not in ORIENTATIONS for orientation in self.orientations):
            raise ValueError("unknown orientation")
        if len(set(self.orientations)) != len(self.orientations):
            raise ValueError("orientations must be unique")
        if not self.phases:
            raise ValueError("at least one phase must be searched")
        if any(not 0 <= phase < KMER_SIZE for phase in self.phases):
            raise ValueError(f"phases must lie in [0, {KMER_SIZE - 1}]")
        if len(set(self.phases)) != len(self.phases):
            raise ValueError("phases must be unique")
        if any(length <= 0 for length in self.window_tokens):
            raise ValueError("window lengths must be positive")
        if len(set(self.window_tokens)) != len(self.window_tokens):
            raise ValueError("window lengths must be unique")
        if self.window_tokens and self.window_stride_tokens <= 0:
            raise ValueError("a positive stride is required when windows are declared")
        if not self.stream_offsets:
            raise ValueError("at least one key-stream offset must be searched")
        if any(offset < 0 for offset in self.stream_offsets):
            raise ValueError("stream offsets must be non-negative")
        if len(set(self.stream_offsets)) != len(self.stream_offsets):
            raise ValueError("stream offsets must be unique")
        if self.minimum_window_tokens <= 0:
            raise ValueError("minimum_window_tokens must be positive")

    def describe(self) -> dict[str, object]:
        """Return a serializable description of the declared search."""

        return {
            "orientations": list(self.orientations),
            "phases": list(self.phases),
            "window_tokens": list(self.window_tokens) or "full_sequence_only",
            "window_stride_tokens": self.window_stride_tokens,
            "stream_offsets": list(self.stream_offsets),
            "minimum_window_tokens": self.minimum_window_tokens,
        }


@dataclass(frozen=True, slots=True)
class DetectorHypothesis:
    """One fully specified alignment the detector actually scored."""

    orientation: str
    phase: int
    window_start: int
    window_tokens: int
    stream_offset: int


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """The maximum statistic over the complete declared search."""

    statistic: float
    matches: int
    total: int
    hypothesis: DetectorHypothesis
    hypotheses_searched: int

    @property
    def agreement_rate(self) -> float:
        return self.matches / self.total if self.total else 0.0


class PartitionCache:
    """Cache keyed partitions by stream position.

    A partition depends on the key, the domain, and the stream index — never on
    the observed token — so one cache entry serves every hypothesis that reads
    that stream position. This is what makes the full search affordable.
    """

    __slots__ = ("_cache", "_stream", "_support")

    def __init__(self, stream: KeyedPartitionStream, support: Sequence[str]) -> None:
        if not support:
            raise ValueError("support must not be empty")
        self._stream = stream
        self._support = tuple(support)
        self._cache: dict[int, tuple[dict[str, bool], bool]] = {}

    def group_and_bit(self, stream_index: int) -> tuple[dict[str, bool], bool]:
        cached = self._cache.get(stream_index)
        if cached is None:
            cached = (
                self._stream.partition(self._support, stream_index),
                self._stream.latent_bit(stream_index),
            )
            self._cache[stream_index] = cached
        return cached

    def agrees(self, stream_index: int, token: str) -> bool:
        partition, latent_bit = self.group_and_bit(stream_index)
        group = partition.get(token)
        if group is None:
            raise ValueError("observed a token outside the declared support")
        return group == latent_bit

    @property
    def cached_positions(self) -> int:
        return len(self._cache)


def standardized_agreement(matches: int, total: int) -> float:
    """Return the standardized agreement statistic for one aligned hypothesis."""

    if total <= 0:
        raise ValueError("total must be positive")
    if not 0 <= matches <= total:
        raise ValueError("matches must lie in [0, total]")
    return (2.0 * matches - total) / math.sqrt(total)


def _oriented_sequence(sequence: str, orientation: str) -> str:
    normalized = normalize_dna(sequence)
    return normalized if orientation == FORWARD else reverse_complement(normalized)


def enumerate_search(
    sequence: str,
    config: DetectorConfig,
) -> tuple[tuple[DetectorHypothesis, tuple[str, ...]], ...]:
    """Enumerate every hypothesis the declared search will score, with its tokens."""

    enumerated: list[tuple[DetectorHypothesis, tuple[str, ...]]] = []
    for orientation in config.orientations:
        oriented = _oriented_sequence(sequence, orientation)
        for phase in config.phases:
            tokens = tokenize_fixed(oriented, phase=phase)
            if len(tokens) < config.minimum_window_tokens:
                continue
            spans: list[tuple[int, int]] = [(0, len(tokens))]
            for length in config.window_tokens:
                if length > len(tokens) or length < config.minimum_window_tokens:
                    continue
                for start in range(0, len(tokens) - length + 1, config.window_stride_tokens):
                    spans.append((start, length))
            for start, length in spans:
                window_tokens = tokens[start : start + length]
                for offset in config.stream_offsets:
                    enumerated.append(
                        (
                            DetectorHypothesis(
                                orientation=orientation,
                                phase=phase,
                                window_start=start,
                                window_tokens=length,
                                stream_offset=offset,
                            ),
                            window_tokens,
                        )
                    )
    return tuple(enumerated)


def detect(
    sequence: str,
    support: Sequence[str],
    stream: KeyedPartitionStream,
    config: DetectorConfig,
    *,
    cache: PartitionCache | None = None,
) -> DetectionResult:
    """Score the complete declared search and return its maximum statistic."""

    enumerated = enumerate_search(sequence, config)
    if not enumerated:
        raise ValueError("the declared search scored no hypothesis for this sequence")
    partitions = cache if cache is not None else PartitionCache(stream, support)
    best: DetectionResult | None = None
    for hypothesis, tokens in enumerated:
        matches = sum(
            partitions.agrees(hypothesis.stream_offset + index, token)
            for index, token in enumerate(tokens)
        )
        statistic = standardized_agreement(matches, len(tokens))
        if best is None or statistic > best.statistic:
            best = DetectionResult(
                statistic=statistic,
                matches=matches,
                total=len(tokens),
                hypothesis=hypothesis,
                hypotheses_searched=len(enumerated),
            )
    assert best is not None
    return best


def detect_aligned(
    tokens: Sequence[str],
    support: Sequence[str],
    stream: KeyedPartitionStream,
    *,
    stream_offset: int = 0,
) -> DetectionResult:
    """Score one known alignment. An internal correctness check, not the paper detector."""

    if not tokens:
        raise ValueError("tokens must not be empty")
    cache = PartitionCache(stream, support)
    matches = sum(cache.agrees(stream_offset + index, token) for index, token in enumerate(tokens))
    return DetectionResult(
        statistic=standardized_agreement(matches, len(tokens)),
        matches=matches,
        total=len(tokens),
        hypothesis=DetectorHypothesis(
            orientation=FORWARD,
            phase=0,
            window_start=0,
            window_tokens=len(tokens),
            stream_offset=stream_offset,
        ),
        hypotheses_searched=1,
    )


@dataclass(frozen=True, slots=True)
class Calibration:
    """An empirical decision threshold from null trials of the identical search."""

    threshold: float
    target_false_positive_rate: float
    achieved_false_positive_rate: float
    null_trials: int
    attainable_false_positive_rate: float
    null_statistics_sorted: tuple[float, ...] = field(repr=False)

    @property
    def is_attainable(self) -> bool:
        return self.target_false_positive_rate >= self.attainable_false_positive_rate


def calibrate_threshold(
    null_statistics: Sequence[float],
    target_false_positive_rate: float,
) -> Calibration:
    """Choose the smallest threshold whose empirical null exceedance meets the target.

    The threshold is a null order statistic, so the achieved rate is a multiple of
    ``1 / trials``. A target below ``1 / trials`` is not attainable with this many
    trials and the calibration says so instead of pretending otherwise.
    """

    if not null_statistics:
        raise ValueError("null calibration requires at least one trial")
    if not 0.0 < target_false_positive_rate < 1.0:
        raise ValueError("target false-positive rate must lie in (0, 1)")
    values = sorted(float(value) for value in null_statistics)
    trials = len(values)
    attainable = 1.0 / trials
    threshold = values[-1]
    achieved = 0.0
    for candidate in values:
        exceedances = sum(value > candidate for value in values)
        if exceedances / trials <= target_false_positive_rate:
            threshold = candidate
            achieved = exceedances / trials
            break
    return Calibration(
        threshold=threshold,
        target_false_positive_rate=target_false_positive_rate,
        achieved_false_positive_rate=achieved,
        null_trials=trials,
        attainable_false_positive_rate=attainable,
        null_statistics_sorted=tuple(values),
    )


def empirical_p_value(statistic: float, null_statistics: Sequence[float]) -> float:
    """Return the global p-value of one statistic against null trials of the same search."""

    if not null_statistics:
        raise ValueError("an empirical p-value requires at least one null trial")
    trials = len(null_statistics)
    exceedances = sum(float(value) >= statistic for value in null_statistics)
    return (1 + exceedances) / (1 + trials)


def detection_rate(statistics: Sequence[float], threshold: float) -> float:
    """Return the fraction of trials at or above a calibrated threshold."""

    if not statistics:
        raise ValueError("detection rate requires at least one trial")
    return sum(float(value) >= threshold for value in statistics) / len(statistics)
