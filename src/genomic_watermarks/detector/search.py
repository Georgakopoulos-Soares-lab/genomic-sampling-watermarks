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
from collections.abc import Mapping, Sequence
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


DECISION_RULE = "statistic > threshold"


@dataclass(frozen=True, slots=True)
class WindowedSearchConfig:
    """A declared sliding-window search for resynchronizing after insertions or deletions.

    The key insight this encodes: after `D` net inserted or deleted bases, an
    observed token at read index `i` corresponds to original token `i + (phase +
    D) / 6`. The key position a window needs is therefore its own start index plus
    a small *drift* term, not an arbitrary absolute position. Searching window
    start and absolute key position independently would multiply the hypothesis
    count by the sequence length for no gain; searching start and drift keeps the
    multiplicity proportional to the drift a channel can actually produce.

    Drift is **signed**. Deletions move content left, so a segment after `D`
    deletions needs a positive drift of about `D / 6`. Insertions move content
    right, so a segment after `I` insertions needs a *negative* drift of about
    `-I / 6`. A drift range restricted to non-negative values cannot reach any
    post-insertion segment at all, which is a silent and total failure on the
    insertion channel rather than a loss of power. A hypothesis whose key start
    would be negative is not scorable and is skipped.

    ``window_tokens`` is the set of window lengths scored. Each length uses a
    stride of half its own length, so longer windows cost fewer starts. A window
    length equal to the token count reproduces the unwindowed search, which is why
    the full length should be included to make the windowed search a superset.
    """

    orientations: tuple[str, ...] = ORIENTATIONS
    phases: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    window_tokens: tuple[int, ...] = (32, 64, 128)
    drift_offsets: tuple[int, ...] = tuple(range(16))

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
        if not self.window_tokens:
            raise ValueError("at least one window length must be declared")
        if any(length < 2 for length in self.window_tokens):
            raise ValueError("window lengths must be at least two tokens")
        if len(set(self.window_tokens)) != len(self.window_tokens):
            raise ValueError("window lengths must be unique")
        if not self.drift_offsets:
            raise ValueError("at least one drift offset must be searched")
        if len(set(self.drift_offsets)) != len(self.drift_offsets):
            raise ValueError("drift offsets must be unique")

    def window_starts(self, token_count: int, window: int) -> tuple[int, ...]:
        """Return the start indices scored for one window length."""

        if window > token_count:
            return ()
        stride = max(1, window // 2)
        return tuple(range(0, token_count - window + 1, stride))

    def hypothesis_count(self, base_length: int) -> int:
        """Return the number of hypotheses this search scores for a sequence length.

        Counted per phase rather than once, because a non-zero phase drops the
        final incomplete k-mer and therefore yields one fewer token, which can
        change how many window starts fit.
        """

        if base_length < 0:
            raise ValueError("base length must be non-negative")
        total = 0
        for _orientation in self.orientations:
            for phase in self.phases:
                token_count = max(0, (base_length - phase) // KMER_SIZE)
                for window in self.window_tokens:
                    for start in self.window_starts(token_count, window):
                        total += sum(1 for drift in self.drift_offsets if start + drift >= 0)
        return total

    def describe(self) -> dict[str, object]:
        return {
            "kind": "windowed",
            "orientations": list(self.orientations),
            "phases": list(self.phases),
            "window_tokens": list(self.window_tokens),
            "window_stride_rule": "half of each window length",
            "drift_offsets": list(self.drift_offsets),
            "drift_is_signed": True,
            "key_position_rule": (
                "window start index plus signed drift; a negative key start is not scorable "
                "and is skipped"
            ),
        }


@dataclass(frozen=True, slots=True)
class WindowedHypothesis:
    """One fully specified windowed alignment."""

    orientation: str
    phase: int
    window_start: int
    window_tokens: int
    drift: int

    @property
    def key_start(self) -> int:
        return self.window_start + self.drift


@dataclass(frozen=True, slots=True)
class WindowedDetectionResult:
    """The maximum statistic over a complete declared windowed search."""

    statistic: float
    matches: int
    total: int
    hypothesis: WindowedHypothesis
    hypotheses_searched: int

    @property
    def agreement_rate(self) -> float:
        return self.matches / self.total if self.total else 0.0


def detect_windowed(
    sequence: str,
    support: Sequence[str],
    stream: KeyedPartitionStream,
    config: WindowedSearchConfig,
    *,
    cache: PartitionCache | None = None,
) -> WindowedDetectionResult:
    """Score a declared sliding-window search and return its maximum statistic.

    A window sitting inside an aligned segment is scored on its own tokens only,
    so it is not diluted by the misaligned remainder of the sequence. That is the
    whole point: an indel-corrupted read has short aligned runs, and the
    unwindowed statistic averages them away.
    """

    partitions = cache if cache is not None else PartitionCache(stream, support)
    best: WindowedDetectionResult | None = None
    scored = 0
    for orientation in config.orientations:
        oriented = _oriented_sequence(sequence, orientation)
        for phase in config.phases:
            tokens = tokenize_fixed(oriented, phase=phase)
            token_count = len(tokens)
            for window in config.window_tokens:
                for start in config.window_starts(token_count, window):
                    span = tokens[start : start + window]
                    for drift in config.drift_offsets:
                        key_start = start + drift
                        if key_start < 0:
                            continue
                        matches = sum(
                            partitions.agrees(key_start + index, token)
                            for index, token in enumerate(span)
                        )
                        scored += 1
                        statistic = standardized_agreement(matches, window)
                        if best is None or statistic > best.statistic:
                            best = WindowedDetectionResult(
                                statistic=statistic,
                                matches=matches,
                                total=window,
                                hypothesis=WindowedHypothesis(
                                    orientation=orientation,
                                    phase=phase,
                                    window_start=start,
                                    window_tokens=window,
                                    drift=drift,
                                ),
                                hypotheses_searched=0,
                            )
    if best is None:
        raise ValueError("the declared windowed search scored no hypothesis for this sequence")
    return WindowedDetectionResult(
        statistic=best.statistic,
        matches=best.matches,
        total=best.total,
        hypothesis=best.hypothesis,
        hypotheses_searched=scored,
    )


@dataclass(frozen=True, slots=True)
class Calibration:
    """An empirical decision threshold from null trials of the identical search.

    The decision rule is strict: a sequence is called watermarked when its
    statistic is *greater than* the threshold. The threshold itself is a null
    order statistic, and the statistic lives on a discrete lattice, so ties at
    the threshold are common. Applying a non-strict rule to a threshold chosen by
    a strict criterion would report a smaller false-positive rate than the rule
    actually achieves.
    """

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

    Exceedance is counted with the same strict rule the detector applies,
    ``statistic > threshold``, so the achieved rate is exactly the rate the rule
    delivers on these trials. The threshold is a null order statistic, so the
    achieved rate is a multiple of ``1 / trials``. A target below ``1 / trials``
    is not attainable with this many trials and the calibration says so instead
    of pretending otherwise.
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
    """Return the fraction of trials the decision rule calls watermarked.

    The rule is strict, ``statistic > threshold``, matching how
    ``calibrate_threshold`` counted null exceedances. Using ``>=`` here would
    call ties at the threshold detections and would therefore exceed the
    calibrated false-positive rate, because the threshold is itself a null value
    on a discrete lattice.
    """

    if not statistics:
        raise ValueError("detection rate requires at least one trial")
    return sum(float(value) > threshold for value in statistics) / len(statistics)


def joint_detection_rate_interval(
    positives_by_cluster: Mapping[str, Sequence[float]],
    null_statistics: Sequence[float],
    target_false_positive_rate: float,
    *,
    replicates: int,
    seed: int,
    confidence_level: float = 0.95,
) -> dict[str, float]:
    """Interval for a detection rate that also carries the threshold's uncertainty.

    A detection rate is measured against a threshold *estimated* from null trials.
    Resampling only the positive clusters treats that threshold as known, which
    understates the uncertainty — badly when the positive and null distributions
    are close, and not at all when the margin is large.

    Each replicate therefore resamples the null trials, recalibrates the threshold
    from that resample, and independently resamples the clusters of positives. The
    clustering is preserved: a cluster contributes the mean of its own trials, so
    replicate trials inside a cluster are never treated as independent.
    """

    if not positives_by_cluster:
        raise ValueError("at least one positive cluster is required")
    if len(positives_by_cluster) < 2:
        raise ValueError("at least two positive clusters are required")
    if not null_statistics:
        raise ValueError("null trials are required to recalibrate the threshold")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must lie in (0, 1)")

    import random as _random
    import statistics as _statistics

    clusters = tuple(sorted(positives_by_cluster))
    values = {name: tuple(float(v) for v in positives_by_cluster[name]) for name in clusters}
    if any(not v for v in values.values()):
        raise ValueError("every positive cluster must hold at least one trial")
    nulls = [float(value) for value in null_statistics]
    point = calibrate_threshold(nulls, target_false_positive_rate)
    rng = _random.Random(seed)
    rates: list[float] = []
    for _ in range(replicates):
        resampled_nulls = [nulls[rng.randrange(len(nulls))] for _ in nulls]
        threshold = calibrate_threshold(resampled_nulls, target_false_positive_rate).threshold
        picked = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        rates.append(
            _statistics.fmean(
                _statistics.fmean([float(v > threshold) for v in values[name]]) for name in picked
            )
        )
    rates.sort()
    tail = (1.0 - confidence_level) / 2.0
    observed = _statistics.fmean(
        _statistics.fmean([float(v > point.threshold) for v in values[name]]) for name in clusters
    )
    return {
        "detection_rate": observed,
        "lower": rates[int(tail * (len(rates) - 1))],
        "upper": rates[int((1.0 - tail) * (len(rates) - 1))],
        "clusters": float(len(clusters)),
        "null_trials": float(len(nulls)),
        "replicates": float(replicates),
        "seed": float(seed),
        "confidence_level": confidence_level,
        "threshold": point.threshold,
        "resamples_the_threshold": 1.0,
    }
