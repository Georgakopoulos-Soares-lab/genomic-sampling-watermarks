"""Standalone detectors for the inverse-transform and exponential baselines.

The E8/E9 comparison is only meaningful if all three methods are detected by the
*same* search over the *same* hypothesis space, so this module deliberately reuses
``DetectorConfig`` and ``enumerate_search`` from the partition detector and changes
only the per-token score.

Each method's per-token score has a known null mean and standard deviation, so the
aggregate is standardized the same way the partition statistic is:

``z = (sum(score) - n * mu) / (sd * sqrt(n))``

Standardizing matters here even though every threshold is calibrated empirically,
because the detector reports a *maximum* over hypotheses whose token counts differ
by one across phases. Without standardizing, that maximum would prefer whichever
hypothesis happened to be longer.

The three statistics live on different scales and must never be compared as raw
values; only calibrated detection rates at a common target false-positive rate are
comparable across methods.
"""

from __future__ import annotations

import math
from array import array
from collections.abc import Sequence
from dataclasses import dataclass

from genomic_watermarks.baselines import (
    EXP_SCHEME,
    ITS_SCHEME,
    KeyedBaselineStream,
    exponential_score,
    inverse_transform_score,
)
from genomic_watermarks.detector.search import DetectorConfig, enumerate_search

# ``-log(1 - u)`` is a unit exponential under the null, which fixes both moments.
EXP_NULL_MEAN = 1.0
EXP_NULL_SD = 1.0

# The inverse-transform score is ``1/3 - |R - U|`` for a normalized rank ``R`` and
# an independent keyed uniform ``U``. Under the null the two are independent, so
# the mean is zero by construction and the variance is ``Var|A - B| = 1/6 - 1/9``
# for independent uniforms. ``R`` lives on a grid of 4,096 points rather than the
# continuum, so these are asymptotic in the support size; the discretization error
# is O(1 / K^2) and no threshold depends on it, because every threshold here is
# calibrated from null trials rather than from the normal tail.
ITS_NULL_MEAN = 0.0
ITS_NULL_SD = math.sqrt(1.0 / 18.0)


@dataclass(frozen=True, slots=True)
class BaselineHypothesis:
    """One fully specified alignment scored by a baseline detector."""

    orientation: str
    phase: int
    window_start: int
    window_tokens: int
    stream_offset: int


@dataclass(frozen=True, slots=True)
class BaselineDetectionResult:
    """The maximum standardized score over the complete declared search."""

    scheme: str
    statistic: float
    total_score: float
    total: int
    hypothesis: BaselineHypothesis
    hypotheses_searched: int

    @property
    def mean_score(self) -> float:
        return self.total_score / self.total if self.total else 0.0


class ExponentialScoreCache:
    """Cache ``-log(1 - u)`` by stream position and token.

    The exponential baseline needs one keyed uniform per *observed* token, so the
    cost is independent of the support size. That is the opposite of the
    inverse-transform baseline below.
    """

    __slots__ = ("_cache", "_stream")

    def __init__(self, stream: KeyedBaselineStream) -> None:
        self._stream = stream
        self._cache: dict[tuple[int, str], float] = {}

    def score(self, stream_index: int, token: str) -> float:
        entry = self._cache.get((stream_index, token))
        if entry is None:
            entry = exponential_score(self._stream.token_uniform(stream_index, token))
            self._cache[(stream_index, token)] = entry
        return entry

    @property
    def cached_entries(self) -> int:
        return len(self._cache)


class InverseTransformScoreCache:
    """Cache keyed ranks and uniforms by stream position.

    A keyed permutation depends on the key, the domain, and the stream index, never
    on the observed token, so one entry per position serves every hypothesis that
    reads it. Ranks are stored as a compact integer array indexed by the token's
    position in the canonical support, which keeps a full 512-token search over
    4,096 k-mers within a few megabytes.
    """

    __slots__ = ("_position", "_ranks", "_stream", "_support", "_uniforms")

    def __init__(self, stream: KeyedBaselineStream, support: Sequence[str]) -> None:
        if not support:
            raise ValueError("support must not be empty")
        self._stream = stream
        self._support = tuple(support)
        self._position = {token: index for index, token in enumerate(self._support)}
        if len(self._position) != len(self._support):
            raise ValueError("support tokens must be unique")
        self._ranks: dict[int, array[int]] = {}
        self._uniforms: dict[int, float] = {}

    def _prepare(self, stream_index: int) -> tuple[array[int], float]:
        ranks = self._ranks.get(stream_index)
        if ranks is None:
            permutation = self._stream.permutation(self._support, stream_index)
            buffer = array("i", bytes(4 * len(self._support)))
            for rank, token in enumerate(permutation):
                buffer[self._position[token]] = rank
            ranks = buffer
            self._ranks[stream_index] = ranks
            self._uniforms[stream_index] = self._stream.uniform(stream_index)
        return ranks, self._uniforms[stream_index]

    def score(self, stream_index: int, token: str) -> float:
        position = self._position.get(token)
        if position is None:
            raise ValueError("observed a token outside the declared support")
        ranks, uniform = self._prepare(stream_index)
        return inverse_transform_score(ranks[position], len(self._support), uniform)

    @property
    def cached_positions(self) -> int:
        return len(self._ranks)


def standardized_score(
    total_score: float, total: int, *, null_mean: float, null_sd: float
) -> float:
    """Standardize an aggregate score against its known null moments."""

    if total <= 0:
        raise ValueError("total must be positive")
    if null_sd <= 0.0:
        raise ValueError("null standard deviation must be positive")
    return (total_score - total * null_mean) / (null_sd * math.sqrt(total))


def detect_baseline(
    sequence: str,
    config: DetectorConfig,
    cache: ExponentialScoreCache | InverseTransformScoreCache,
    *,
    scheme: str,
) -> BaselineDetectionResult:
    """Score the complete declared search for one baseline and return its maximum.

    The hypothesis enumeration is shared with the partition detector, so a
    comparison between methods cannot be biased by one method searching fewer
    alignments than another.
    """

    if scheme == EXP_SCHEME:
        null_mean, null_sd = EXP_NULL_MEAN, EXP_NULL_SD
    elif scheme == ITS_SCHEME:
        null_mean, null_sd = ITS_NULL_MEAN, ITS_NULL_SD
    else:
        raise ValueError(f"unknown baseline scheme: {scheme}")

    enumerated = enumerate_search(sequence, config)
    if not enumerated:
        raise ValueError("the declared search scored no hypothesis for this sequence")
    best: BaselineDetectionResult | None = None
    for hypothesis, tokens in enumerated:
        total_score = math.fsum(
            cache.score(hypothesis.stream_offset + index, token)
            for index, token in enumerate(tokens)
        )
        statistic = standardized_score(
            total_score, len(tokens), null_mean=null_mean, null_sd=null_sd
        )
        if best is None or statistic > best.statistic:
            best = BaselineDetectionResult(
                scheme=scheme,
                statistic=statistic,
                total_score=total_score,
                total=len(tokens),
                hypothesis=BaselineHypothesis(
                    orientation=hypothesis.orientation,
                    phase=hypothesis.phase,
                    window_start=hypothesis.window_start,
                    window_tokens=hypothesis.window_tokens,
                    stream_offset=hypothesis.stream_offset,
                ),
                hypotheses_searched=len(enumerated),
            )
    assert best is not None
    return best


def baseline_cache(
    scheme: str,
    stream: KeyedBaselineStream,
    support: Sequence[str],
) -> ExponentialScoreCache | InverseTransformScoreCache:
    """Return the score cache the named baseline detector needs."""

    if scheme == EXP_SCHEME:
        return ExponentialScoreCache(stream)
    if scheme == ITS_SCHEME:
        return InverseTransformScoreCache(stream, support)
    raise ValueError(f"unknown baseline scheme: {scheme}")
